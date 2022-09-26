# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class SendForApproval(models.TransientModel):
    _name = 'approval.send'
    _description = "Send For Approval"

    user_id = fields.Many2one('res.users', 'First approval User')
    second_user_id = fields.Many2one('res.users', 'Second Approver User')
    second_user_bool = fields.Boolean('Second Approver Bool')
    purchase_id = fields.Many2one('purchase.order', 'PO', default=lambda self: self.env.context.get('active_id', False))
    
    @api.onchange('user_id')
    def _onchange_user_id(self):
        active_id = self.env.context.get('active_id')
        purchase_id = self.env['purchase.order'].sudo().search([('id', '=', active_id)])
        domain = [('id', '!=', self.env.user.id)]
        second_users_domain = [('id', '!=', self.env.user.id)]
        users = []
        if purchase_id.currency_id.name == 'NZD':
            amount = purchase_id.amount_total
        else:
            to_currency_id = self.env['res.currency'].sudo().search([('name', '=', 'NZD')], limit=1)
            nzd_company_id = self.env['res.company'].sudo().search([('currency_id.name', '=', 'NZD')], limit=1)
            amount = purchase_id.currency_id._convert(purchase_id.amount_total, to_currency_id, nzd_company_id,
                                                      fields.Date.today())
        if purchase_id:
            if not purchase_id.analytic_account_id and purchase_id.partner_id.approval_id:
                approval_id = purchase_id.partner_id.approval_id
            elif purchase_id.analytic_account_id and purchase_id.analytic_account_id.approval_id:
                approval_id = purchase_id.analytic_account_id.approval_id
            else:
                approval_id = purchase_id.company_id.approval_id
            if approval_id:
                users = approval_id.sudo().approval_user_ids.filtered(lambda a:a.from_amount <= amount and a.to_amount >= amount).mapped('user_ids')
                user_approval_line = approval_id.sudo().approval_user_ids.filtered(lambda a:a.from_amount <= amount and a.to_amount >= amount)
                if user_approval_line.required_second_approval == 'yes':
                    self.second_user_bool = True
                else:
                    self.second_user_bool = False
                second_users = user_approval_line.mapped('second_approver_user_ids')
            if users:
                domain += [('id', 'in', users.ids)]
                second_users_domain += [('id', 'in', second_users.ids)]
            else:
                domain += [('id', '=', False)]
                second_users_domain += [('id', 'in', False)]
        return{'domain':{
                    'user_id':domain,
                    'second_user_id':second_users_domain,
                    }
                }

    def confirm(self):
        active_id = self.env.context.get('active_id')
        purchase_id = self.env['purchase.order'].search([('id', '=', active_id)])
        if purchase_id:
            template = self.env.ref('multi_po_approval.mail_template_purchase_first_approval', raise_if_not_found=False)
            purchase_id.state = 'first_approval_sent'
            purchase_id.approval_user_id = self.user_id.id
            purchase_id.approval_second_user_id = self.second_user_id.id
            template.send_mail(purchase_id.id,force_send=True)
