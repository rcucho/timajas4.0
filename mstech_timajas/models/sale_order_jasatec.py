from odoo import models,fields,api,_
from odoo.exceptions import UserError

class SaleOrderJasatec(models.Model):
    _inherit = 'sale.order'
    
    def open_return(self):
        mant = super().open_return()

        for rec in self.order_line:
            rec._timesheet_create_task(self.env.ref('mstech_timajas.project_project_maintenance'))

        return mant

    
