from odoo import models,fields,api,_
from datetime import timedelta, datetime
from odoo.exceptions import UserError
from collections import defaultdict

class ProjectTaskTimajas(models.Model):
    _inherit = "project.task"
    
    create_function = fields.Char(related='create_uid.function', readonly=True)
    state_payment_invoice = fields.Selection(related='sale_order_id.invoice_ids.payment_state',string="Invoice Payment Status" ,readonly=True)  
    #------------------------------------------------------------------------------------------------------------------------------------------
    task_picking = fields.One2many('stock.picking','picking_task', string="Warehouse Request")
    om_mrp = fields.One2many('mrp.production','om_project',string="Manufacturing Order")
    proj_mant = fields.One2many('maintenance.request','mant_project',string="Maintenance Request")
    #------------------------------------------------------------------------------------------------------------------------------------------
    task_eqip = fields.Many2one('maintenance.equipment', string="Tasks in Equipments", compute='_compute_task_eqip')
    total_cost_emp = fields.Monetary(string="Total Cost", compute='_onchange_total_cost_emp')
    total_cost_stck = fields.Monetary(string="Total Cost Warehouse Request", compute='_onchange_total_cost_stck')
    #------------------------------------------------------------------------------------------------------------------------------------------
    @api.onchange('task_picking')
    def _onchange_total_cost_stck(self):
        for record in self:
            cost_pick = 0         
            picking_ids = record.task_picking
            for picking in picking_ids:
                cost_move = 0
                if picking.state == 'done' and picking.type_in_out =='count':
                    moves_ids = picking.move_ids_without_package
                    for moves in moves_ids:
                        cost_move = cost_move + (moves.product_id.standard_price * moves.quantity_done)
                cost_pick = cost_pick + cost_move
            record.total_cost_stck = cost_pick
    #------------------------------------------------------------------------------------------------------------------------------------------
    @api.onchange('proj_mant')
    def _compute_task_eqip(self):
        for rec in self:
            rec.task_eqip = rec.proj_mant.equipment_id
    #------------------------------------------------------------------------------------------------------------------------------------------
    @api.onchange('timesheet_ids')
    def _onchange_total_cost_emp(self):
        for record in self:
            #if record.timesheet_ids:
            record.total_cost_emp = round(sum(record.timesheet_ids.mapped('amount_wo_aa')), 2)
    #==========================================================================================================================================
    @api.onchange('om_mrp')
    def onchange_origin_location(self):
        #self.ensure_one()
        for record in self:
            #manufacture = record.om_mrp
            manufacture_ids = record.om_mrp
            if record.sale_order_id:
                sale_order = record.sale_order_id
                for manufacture in manufacture_ids:
                    if manufacture.sale_order_count == 0:
                        if manufacture.state == 'done':
                            #manufacture.sale_order_count = 1
                            #if manufacture.project_mrp_sale_bool == False:
                            sale_order_line = {
                                'order_id': sale_order.id,
                                'product_id': manufacture.product_id.id,
                                'price_unit': manufacture.product_id.list_price,
                                'product_uom_qty': manufacture.product_qty,
                                #'qty_delivered' : manufacture.product_qty,
                                'tax_id': manufacture.product_id.taxes_id,
                                'is_downpayment': False,
                                'discount': 0.0,
                                #'task_id' : record.id,
                            }
                            self.env['sale.order.line'].create(sale_order_line)
                                #manufacture.project_mrp_sale_bool = True
#==============================================4/2/22===============================================================================
    @api.model_create_multi
    def create(self,values):
        res = super().create(values)
        for record in res:
            if record.sale_line_id.order_id:
                mrp_info = record.sale_line_id.order_id.action_view_mrp_production()
                mrp_ids = mrp_info.get('res_id',mrp_info.get('domain',[(False,False,False)])[0][2])
                if mrp_ids:
                    self.env['mrp.production'].browse(mrp_ids).write({'om_project' : record.id})
        return res
    #==============================================4/2/22===============================================================================
class MrpProducction(models.Model):
    _inherit = "mrp.production"
    om_project = fields.Many2one('project.task', string="OM en Proyecto")
    #project_mrp_sale = fields.Boolean(string="MRP creada por Tarea para venta")
    #---------------------------------------------------------------------------------------------------------------------------------    
    @api.onchange('om_project', 'product_id')
    def onchange_origin_location(self):
        for record in self:
            if record.om_project:
                record.origin = record.om_project.name #+ " / " + record.om_project.sale_order_id.name
                #if record.state == 'done':
                    #record.project_mrp_sale_bool = True
    #---------------------------------------------------------------------------------------------------------------------------------
class StockPickingTask(models.Model):
    _inherit = 'stock.picking'   
    picking_task = fields.Many2one('project.task', string="tarea en movimiento")
    has_auth_bol = fields.Boolean(string="Authorized")
    has_auth =fields.Selection([('blocked','Denied'),('done','Approved'),('normal','Waiting')], string="Authorized", compute='onchange_has_auth')
    type_in_out = fields.Selection([('count', 'Count'),('no_count', 'No Count')], string="Counting?")
    state = fields.Selection(selection_add=[('no_auth', 'No Auth'),('assigned',),], ondelete={'no_auth': 'cascade'})
    #product_stk_cost = fields.Float(string="Cost", related='product_id.standard_price')
    
    @api.model
    def create(self, vals):
        defaults = self.default_get(['name', 'picking_type_id'])
        picking_type = self.env['stock.picking.type'].browse(vals.get('picking_type_id', defaults.get('picking_type_id')))             
        if self.picking_task:
            if vals.get('name', '/') == '/' and defaults.get('name', '/') == '/' and vals.get('picking_type_id', defaults.get('picking_type_id')):
                vals['name'] = picking_type.sequence_id.next_by_id()
        res = super().create(vals)
        return res
    #----------------------------------------------------------------------------------------------------------------------------------------------
    @api.onchange('has_auth_bol')
    def onchange_has_auth(self):
        for record in self:
            if record.has_auth_bol == True:
                record.has_auth = 'done'
            else:
                if record.state == 'done':
                    record.has_auth = 'done'
                else:
                    record.has_auth = 'normal'     
    #----------------------------------------------------------------------------------------------------------------------------------------------
    @api.onchange('picking_type_id', 'partner_id')
    def onchange_picking_type(self):
        for record in self:
            if record.picking_task:
                record.picking_type_id = (5, 'San Francisco: Internal Transfers')
    #----------------------------------------------------------------------------------------------------------------------------------------------
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        for record in self:
            if record.picking_task:
                record.partner_id = record.picking_task.partner_id
        parti = None
        if hasattr(super(), 'onchange_partner_id'):
            parti = super().onchange_partner_id()
        return parti
    
    @api.depends('state', 'move_lines', 'move_lines.state', 'move_lines.package_level_id', 'move_lines.move_line_ids.package_level_id')
    def _compute_move_without_package(self):
        for record in self:
            if record.picking_task:
                movimi = record.move_ids_without_package       
                pass
        mov_he = super()._compute_move_without_package()
        return mov_he

    def button_auth(self):
        for picking in self:
            #if picking.state == 'assigned':
            if picking.state == 'no_auth':
                picking.has_auth_bol = True
        return True
    
    @api.depends('state')
    def _compute_show_validate(self):
        for picking in self:
            if not (picking.immediate_transfer) and picking.state == 'draft':
                picking.show_validate = False
            elif picking.state == 'no_auth':
                picking.show_validate = False
            elif picking.state == 'assigned':
                picking.show_validate = True
            #elif picking.has_auth_bol == True and picking.state =='assigned':
                #picking.show_validate = True                
            elif picking.state not in ('draft', 'waiting', 'confirmed', 'assigned'):
                picking.show_validate = False
            else:
                picking.show_validate = True
    #----------------------------------------------------------------------------------------------------------------------------------------------
    @api.depends('move_type', 'immediate_transfer', 'move_lines.state', 'move_lines.picking_id','has_auth_bol')
    def _compute_state(self):
        ''' State of a picking depends on the state of its related stock.move
        - Draft: only used for "planned pickings"
        - Waiting: if the picking is not ready to be sent so if
          - (a) no quantity could be reserved at all or if
          - (b) some quantities could be reserved and the shipping policy is "deliver all at once"
        - Waiting another move: if the picking is waiting for another move
        - Ready: if the picking is ready to be sent so if:
          - (a) all quantities are reserved or if
          - (b) some quantities could be reserved and the shipping policy is "as soon as possible"
        - Done: if the picking is done.
        - Cancelled: if the picking is cancelled
        '''
        picking_moves_state_map = defaultdict(dict)
        picking_move_lines = defaultdict(set)
        for move in self.env['stock.move'].search([('picking_id', 'in', self.ids)]):
            picking_id = move.picking_id
            move_state = move.state
            picking_moves_state_map[picking_id.id].update({
                'any_draft': picking_moves_state_map[picking_id.id].get('any_draft', False) or move_state == 'draft',
                'all_cancel': picking_moves_state_map[picking_id.id].get('all_cancel', True) and move_state == 'cancel',
                'all_cancel_done': picking_moves_state_map[picking_id.id].get('all_cancel_done', True) and move_state in ('cancel', 'done'),
            })
            picking_move_lines[picking_id.id].add(move.id)
        for picking in self:
            picking_id = (picking.ids and picking.ids[0]) or picking.id
            if not picking_moves_state_map[picking_id]:
                picking.state = 'draft'
            elif picking_moves_state_map[picking_id]['any_draft']:
                picking.state = 'draft'
            elif picking_moves_state_map[picking_id]['all_cancel']:
                picking.state = 'cancel'
            elif picking_moves_state_map[picking_id]['all_cancel_done']:
                picking.state = 'done'
            else:
                relevant_move_state = self.env['stock.move'].browse(picking_move_lines[picking_id])._get_relevant_state_among_moves()
                if picking.immediate_transfer and relevant_move_state not in ('draft', 'cancel', 'done'):
                    if picking.has_auth_bol:
                        picking.state = 'assigned'
                    else:
                        picking.state = 'no_auth'
                elif relevant_move_state == 'partially_available':
                    if picking.has_auth_bol:
                        picking.state = 'assigned'
                    else:
                        picking.state = 'no_auth'
                else:
                    if picking.has_auth_bol:
                        picking.state = relevant_move_state
                    else:
                        picking.state = 'no_auth'

class StockPickingTask(models.Model):
    _inherit = 'account.analytic.line'
    
    amount_wo_aa = fields.Monetary(string="Cost Part Hour", compute='_compute_amount_wo_aa')
    emp_cost_hour = fields.Monetary(string="Cost per Employee", related = 'employee_id.timesheet_cost')
    
    @api.onchange('employee_id')
    def _compute_amount_wo_aa(self):
        for record in self:
            emp_cost = record._employee_timesheet_cost()
            #if record.employee_id:
            monto = record.unit_amount * emp_cost
            record.amount_wo_aa = record.employee_id.currency_id._convert(monto, record.currency_id, self.env.company, record.date)
