# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014 Smile (<http://www.smile.fr>). All Rights Reserved
#                       author cyril.defaria@smile.fr
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import (orm, fields)
from openerp.tools import ustr
from openerp.tools.translate import _

from openerp.addons.connector.unit.mapper import backend_to_m2o
from openerp.addons.connector.unit.mapper import mapping
from openerp.addons.magentoerpconnect.unit.mapper import normalize_datetime
from openerp.addons.magentoerpconnect.sale import SaleOrderImport, SaleOrderImportMapper, SaleOrderLineImportMapper, SaleOrderAdapter
from openerp.addons.magentoerpconnect.backend import magento

from datetime import date
import logging
_logger = logging.getLogger(__name__)


class ECommerceSaleOrder(orm.Model):
    _inherit = 'sale.order'

    _columns = {
        'write_date': fields.datetime('Last Update Date', readonly=True),
        'payment_reference': fields.char('Payment Reference', size=64),
    }


#     def create_sale_order_from_dict(self, order_data):
#
#         # Be sure the structure of the order_data is correct
#
#         order_required_fields = ['customer_id', 'shipping_address_id', 'billing_address_id',
#                                  'created_at', 'store_id', 'magento_sale_order_ref',
#                                  'payment_terms_id', 'payment_reference', 'lines']
#         line_required_fields = ['quantity', 'price', 'tax_id', 'description']
#
#         for field in order_required_fields:
#             if not field in order_data:
#                 _logger.error(_('Cannot create a sale order because field {} is missing'.format(field)))
#
#         for field in line_required_fields:
#             if not field in order_data['lines']:
#                 _logger.error(_('Cannot create a sale order line because field {} is missing'.format(field)))


    def validate_sale_orders(self, cr, uid, ids, sale_order, context=None):
        if sale_order.payment_terms_id.id == 2 :  # CB
            # Créer facture : Sur le bon de livraison - Politique d'expédition : Tout en une fois
            sale_order.write({'ignore_exceptions': True}, context=context)
            sale_order.action_button_confirm(context=context)


@magento(replacing=SaleOrderImport)
class ECommerceSaleOrderImport(SaleOrderImport):

    def _before_import(self):
        pass

    def _after_import(self, binding_id):
        """ We confirm the sale order and the picking out """
        super(ECommerceSaleOrderImport, self)._after_import(binding_id)
        sale_order = self.session.browse('magento.sale.order', binding_id).openerp_id

        # Validation
        sale_order.validate_sale_orders(sale_order, context=self.session.context)
#         for picking in sale_order.picking_ids:
#             if picking.type == 'out':
#                 picking.validate_picking_out()

    def _get_magento_data(self):

        sale_order = {
            "customer_id": 1,
            "shipping_address_id": 2,
            "billing_address_id": 3,
            "created_at": '02/10/2014',
            "shop_id": 1,
            "ecommerce_sale_order_ref": "IdOnMagento",
            "payment_terms": "CB",
            "shipping_method": "ecopli",
            "payment_reference": "PaymentReferenceOnMagento",
            "order_policy": "picking",
            "picking_policy": "one",

            "lines": [
            {
                "qty": 5,
                "price": 5,
                "taxes": ['20.0'],
                "description": "product_5",
                "gift": True,
                "product_id": "",
                "discount": ""
            },
            {
                "qty": 10,
                "price": 10,
                "taxes": [],
                "description": "product_10",
                "gift": "",
                "product_id": "",
                "discount": 5.0,
            }
            ]
        }
        return sale_order

    def _import_dependencies(self):
        pass

@magento(replacing=SaleOrderImportMapper)
class EcommerceSaleOrderImportMapper(SaleOrderImportMapper):

    direct = [
              (backend_to_m2o('customer_id', binding="magento.res.partner"), 'partner_id'),
              (backend_to_m2o('shipping_address_id', binding="magento.res.partner"), 'partner_shipping_id'),
              (backend_to_m2o('billing_address_id', binding="magento.res.partner"), 'partner_invoice_id'),
              (normalize_datetime('created_at'), 'date_order'),
              (backend_to_m2o('shop_id', binding="magento.store"), 'shop_id'),
              ('ecommerce_sale_order_ref', 'client_order_ref'),
              ('payment_reference', 'payment_reference'),
             ]

    children = [('lines', 'magento_order_line_ids', 'magento.sale.order.line')]

    @mapping
    def payment(self, record):
        session = self.session
        ecommerce_payment_mode = record['payment_terms']
        payment_mode = session.pool.get('payment.terms.partner').search(session.cr, session.uid, [('code', '=', ecommerce_payment_mode)],
                                                                        context=session.context)
        if not payment_mode:
            raise MappingError(_('The payment mode {} does not exist'.format(ecommerce_payment_mode)))
        return {'payment_terms_id': payment_mode[0]}

    @mapping
    def order_policy(self, record):
        order_policy = record['order_policy']
        if order_policy and order_policy not in ['manual', 'picking', 'prepaid']:
            raise MappingError(_('The order policy {} does not exist'.format(order_policy)))
        return {'order_policy': order_policy or 'picking'}

    @mapping
    def picking_policy(self, record):
        picking_policy = record['picking_policy']
        if picking_policy and picking_policy not in ['direct', 'one']:
            raise MappingError(_('The picking policy {} does not exist'.format(picking_policy)))
        return {'picking_policy': picking_policy or 'one'}

    # We use the original shipping_method for the shipping mapping (in the module magentoerpconnect)
    # But what does "sale_order_comment" ?

    # Overwrite original connector methods we don't need (anymore)

    @mapping
    def name(self, record):
        """We want to keep the OpenERP sequence, not use the Magento one"""
        return {}

    @mapping
    def store_id(self, record):
        """Overwrite"""
        pass

    @mapping
    def customer_id(self, record):
        """Overwrite"""
        pass


@magento(replacing=SaleOrderLineImportMapper)
class ECommerceSaleOrderLineImportMapper(SaleOrderLineImportMapper):

    direct = [
              (backend_to_m2o('product_id', binding="magento.product.product"), 'product_id'),
              ('quantity', 'product_uom_qty'),
              ('price', 'price_unit'),
              ('description', 'name'),
              ('discount', 'discount'),
             ]

    @mapping
    def taxes(self, record):
        session = self.session
        taxes_mapping = session.pool.get('account.taxes')
        ecommerce_taxes = record['taxes']
        if ecommerce_taxes:
            tax_ids = taxes_mapping.search(session.cr, session.uid, [('description', 'in', ecommerce_taxes)], context=session.context)
            if tax_ids:
                return {'tax_id': [(6, 0, tax_ids)]}

    @mapping
    def gift_wrapping(self, record):
        if record.get('gift'):
            gift_id = self.session.search('product.product', [('name', '=', 'Emballage cadeau')])[0]
            return {'product_giftwrap_id': gift_id}

    @mapping
    def product_options(self, record):
        """No Options"""
        pass

    @mapping
    def price(self, record):
        """Overwrite"""
        pass

    @mapping
    def discount_amount(self, record):
        """Overwrite"""
        pass

    @mapping
    def product_id(self, record):
        """Overwrite"""
        pass


@magento(replacing=SaleOrderAdapter)
class EcommerceSaleOrderAdapter(SaleOrderAdapter):
    _model_name = 'magento.sale.order'

    def read(self, id, attributes=None):
        """ Returns the information of a record """
        record = self._call('oe_order.order_info_OE', [str(id)])
        return record

    def search(self, filters=None, from_date=None, to_date=None,
               magento_storeview_ids=None):
        return [1]