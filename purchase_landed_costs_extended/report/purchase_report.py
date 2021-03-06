# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (c) 2010-2014 Elico Corp. All Rights Reserved.
#    Augustin Cisterne-Kaas <augustin.cisterne-kaas@elico-corp.com>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
#
# Please note that these reports are not multi-currency !!!
#
from openerp.osv import fields, orm
from openerp import tools


class purchase_landed_cost_report(orm.Model):
    _name = "purchase.landed.cost.report"
    _description = "Purchases Orders"
    _auto = False
    _columns = {
        'date': fields.date(
            'Order Date', readonly=True,
            help="Date on which this document has been created"),
        'name': fields.char('Year', size=64, required=False, readonly=True),
        'day': fields.char('Day', size=128, readonly=True),
        'state': fields.selection([
            ('draft', 'Request for Quotation'),
            ('confirmed', 'Waiting Supplier Ack'),
            ('approved', 'Approved'),
            ('except_picking', 'Shipping Exception'),
            ('except_invoice', 'Invoice Exception'),
            ('done', 'Done'),
            ('cancel', 'Cancelled')],
            'Order Status', readonly=True),
        'product_id': fields.many2one(
            'product.product', 'Product', readonly=True),
        'warehouse_id': fields.many2one(
            'stock.warehouse', 'Warehouse', readonly=True),
        'location_id': fields.many2one(
            'stock.location', 'Destination', readonly=True),
        'partner_id': fields.many2one(
            'res.partner', 'Supplier', readonly=True),
        'pricelist_id': fields.many2one(
            'product.pricelist', 'Pricelist', readonly=True),
        'date_approve': fields.date(
            'Date Approved', readonly=True),
        'expected_date': fields.date(
            'Expected Date', readonly=True),
        'validator': fields.many2one(
            'res.users', 'Validated By', readonly=True),
        'product_uom': fields.many2one(
            'product.uom', 'Reference Unit of Measure', required=True),
        'company_id': fields.many2one(
            'res.company', 'Company', readonly=True),
        'user_id': fields.many2one(
            'res.users', 'Responsible', readonly=True),
        'quantity': fields.float('Quantity', readonly=True),
        'price_total': fields.float('Total Price', readonly=True),
        'price_average': fields.float(
            'Average Price', readonly=True,
            group_operator="avg"),
        'negociation': fields.float(
            'Purchase-Standard Price', readonly=True,
            group_operator="avg"),
        'price_standard': fields.float(
            'Products Value', readonly=True,
            group_operator="sum"),
        'nbr': fields.integer('# of Lines', readonly=True),
        'month': fields.selection(
            [
                ('01', 'January'), ('02', 'February'), ('03', 'March'),
                ('04', 'April'), ('05', 'May'), ('06', 'June'),
                ('07', 'July'), ('08', 'August'), ('09', 'September'),
                ('10', 'October'), ('11', 'November'), ('12', 'December')
            ], 'Month', readonly=True),
        'category_id': fields.many2one('product.category', 'Category',
                                       readonly=True),
        'landed_cost_total': fields.float(
            'Landed cost total', readonly=True,
            group_operator="sum"),
        'landed_cost_unit': fields.float(
            'Landed cost unit', readonly=True,
            group_operator="sum"),
        'purchase_order_id': fields.many2one(
            'purchase.order', 'Purchase Order', readonly=True),
    }
    _order = 'name desc,price_total desc'

    def init(self, cr):
        tools.sql.drop_view_if_exists(cr, 'purchase_landed_cost_report')
        cr.execute("""
            CREATE OR REPLACE FUNCTION po_landed_cost_per_unit(int)
            RETURNS numeric
                AS '
            SELECT sum(subtotal) FROM (SELECT

                                         ((po_lcp.amount_company_currency
                                          / (SELECT sum(product_qty) FROM
                                            purchase_order_line
                                            WHERE order_id = pol.order_id))
                                          * pol.product_qty
                                    ) as subtotal
                                    FROM purchase_order_line POL
                                    LEFT JOIN landed_cost_position po_lcp
                                    ON po_lcp.purchase_order_id = pol.order_id
                                    LEFT JOIN landed_cost_distribution_type
                                    po_lcdt
                                    ON po_lcdt.id = po_lcp.distribution_type_id
                                    WHERE pol.id = $1
                                    AND po_lcp.active = true
                                    AND po_lcp.purchase_order_line_id is null
                                    AND po_lcdt.landed_cost_type = ''per_unit''
                                    GROUP BY pol.id, po_lcp.id, po_lcdt.id)
                                    as result'
                       LANGUAGE SQL;

            CREATE OR REPLACE FUNCTION po_landed_cost_per_value(int)
            RETURNS numeric
                AS '
                    SELECT sum(subtotal)
                    FROM (
                        SELECT (
                            (po_lcp.amount_company_currency
                                * (pol.price_unit
                                * pol.product_qty)) / po.amount_untaxed
                        ) as subtotal
                        FROM purchase_order_line POL
                        LEFT JOIN purchase_order po
                        ON po.id = pol.order_id
                        LEFT JOIN landed_cost_position po_lcp
                        ON po_lcp.purchase_order_id = pol.order_id
                        LEFT JOIN landed_cost_distribution_type po_lcdt
                        ON po_lcdt.id = po_lcp.distribution_type_id
                        WHERE pol.id = $1
                            AND po_lcp.active = true
                            AND po_lcp.purchase_order_line_id is null
                            AND po_lcdt.landed_cost_type = ''value''
                        GROUP BY pol.id, po.id, po_lcp.id, po_lcdt.id) as
                        result'
            LANGUAGE SQL;


            CREATE OR REPLACE FUNCTION pol_landed_cost_per_unit(int) RETURNS
            numeric
                AS '
                    SELECT sum(subtotal)
                    FROM (
                        SELECT
                                    pol.id as polid,
                                    (
                                        pol_lcp.amount_company_currency
                                        * pol.product_qty
                                    ) as subtotal
                                    FROM purchase_order_line POL
                                    LEFT JOIN landed_cost_position pol_lcp
                                    ON pol_lcp.purchase_order_line_id = pol.id
                                    LEFT JOIN landed_cost_distribution_type
                                    pol_lcdt
                                    ON
                                    pol_lcdt.id = pol_lcp.distribution_type_id
                                    WHERE pol.id = $1
                                    AND pol_lcp.active = true
                                    AND
                                    pol_lcdt.landed_cost_type = ''per_unit''
                                    GROUP BY pol.id, pol_lcp.id, pol_lcdt.id)
                                    as result'
            LANGUAGE SQL;

            CREATE OR REPLACE FUNCTION pol_landed_cost_per_value(int) RETURNS
            numeric
                AS 'SELECT sum(subtotal)
                    FROM (
                            SELECT
                                    pol.id as polid,
                                    pol_lcp.amount_company_currency as subtotal
                                    FROM purchase_order_line POL
                                    LEFT JOIN landed_cost_position pol_lcp
                                    ON pol_lcp.purchase_order_line_id = pol.id
                                    LEFT JOIN landed_cost_distribution_type
                                    pol_lcdt
                                    ON
                                    pol_lcdt.id = pol_lcp.distribution_type_id
                                    WHERE pol.id = $1
                                    AND pol_lcp.active = true
                                    AND pol_lcdt.landed_cost_type = ''value''
                                    GROUP BY pol.id, pol_lcp.id, pol_lcdt.id)
                                    as result'
            LANGUAGE SQL;


            CREATE OR REPLACE FUNCTION pol_landed_cost_total(int) RETURNS
            numeric
                AS 'SELECT sum(subtotal)
                    FROM (select po_landed_cost_per_unit as subtotal
                        from po_landed_cost_per_unit($1) UNION
            select po_landed_cost_per_value as subtotal
            from po_landed_cost_per_value($1) UNION
            select pol_landed_cost_per_unit as subtotal
            from pol_landed_cost_per_unit($1) UNION
            select pol_landed_cost_per_value as subtotal
            from pol_landed_cost_per_value($1)) as result'
            LANGUAGE SQL;

            CREATE OR REPLACE FUNCTION single_pol_po_landed_cost_per_unit(int)
            RETURNS numeric
                AS '
            SELECT sum(subtotal) FROM (SELECT

                                         ((po_lcp.amount_company_currency
                                          / (SELECT sum(product_qty) FROM
                                            purchase_order_line WHERE
                                            order_id = pol.order_id))
                                    ) as subtotal
                                    FROM purchase_order_line POL
                                    LEFT JOIN landed_cost_position po_lcp
                                    ON po_lcp.purchase_order_id = pol.order_id
                                    LEFT JOIN landed_cost_distribution_type
                                    po_lcdt
                                    ON po_lcdt.id = po_lcp.distribution_type_id
                                    WHERE pol.id = $1
                                    AND po_lcp.active = true
                                    AND po_lcp.purchase_order_line_id is null
                                    AND po_lcdt.landed_cost_type = ''per_unit''
                                    GROUP BY pol.id, po_lcp.id, po_lcdt.id)
                                    as result'
                       LANGUAGE SQL;
            CREATE OR REPLACE FUNCTION single_pol_po_landed_cost_per_value(int)
            RETURNS numeric
                AS '
                    SELECT sum(subtotal)
                    FROM (
                        SELECT (
                            (po_lcp.amount_company_currency * pol.price_unit) /
                            po.amount_untaxed
                        ) as subtotal
                        FROM purchase_order_line POL
                        LEFT JOIN purchase_order po
                        ON po.id = pol.order_id
                        LEFT JOIN landed_cost_position po_lcp
                        ON po_lcp.purchase_order_id = pol.order_id
                        LEFT JOIN landed_cost_distribution_type po_lcdt
                        ON po_lcdt.id = po_lcp.distribution_type_id
                        WHERE pol.id = $1
                            AND po_lcp.active = true
                            AND po_lcp.purchase_order_line_id is null
                            AND po_lcdt.landed_cost_type = ''value''
                        GROUP BY pol.id, po.id, po_lcp.id, po_lcdt.id)
                        as result'
            LANGUAGE SQL;


            CREATE OR REPLACE FUNCTION single_pol_landed_cost_per_unit(int)
            RETURNS numeric
                AS '
                    SELECT sum(subtotal)
                    FROM (
                        SELECT
                                    pol.id as polid,
                                    pol_lcp.amount_company_currency as subtotal
                                    FROM purchase_order_line POL
                                    LEFT JOIN landed_cost_position pol_lcp
                                    ON pol_lcp.purchase_order_line_id = pol.id
                                    LEFT JOIN landed_cost_distribution_type
                                    pol_lcdt
                                    ON
                                    pol_lcdt.id = pol_lcp.distribution_type_id
                                    WHERE pol.id = $1
                                    AND pol_lcp.active = true
                                    AND
                                    pol_lcdt.landed_cost_type = ''per_unit''
                                    GROUP BY pol.id, pol_lcp.id, pol_lcdt.id)
                                    as result'
            LANGUAGE SQL;

           CREATE OR REPLACE FUNCTION single_pol_landed_cost_per_value(int) RETURNS
            numeric
                AS 'SELECT sum(subtotal)
                    FROM (
                            SELECT
                                    pol.id as polid,
                                    (
                                        pol_lcp.amount_company_currency /
                                        pol.product_qty
                                    )as subtotal
                                    FROM purchase_order_line POL
                                    LEFT JOIN landed_cost_position pol_lcp
                                    ON pol_lcp.purchase_order_line_id = pol.id
                                    LEFT JOIN landed_cost_distribution_type
                                    pol_lcdt
                                    ON
                                    pol_lcdt.id = pol_lcp.distribution_type_id
                                    WHERE pol.id = $1
                                    AND pol_lcp.active = true
                                    AND pol_lcdt.landed_cost_type = ''value''
                                    GROUP BY pol.id, pol_lcp.id, pol_lcdt.id)
                                    as result'
            LANGUAGE SQL;
            CREATE OR REPLACE FUNCTION pol_landed_cost_unit(int)
            RETURNS numeric
                AS 'SELECT sum(subtotal)
                    FROM (select single_pol_po_landed_cost_per_unit as subtotal
                        from single_pol_po_landed_cost_per_unit($1) UNION
            select single_pol_po_landed_cost_per_value as subtotal
            from single_pol_po_landed_cost_per_value($1) UNION
            select single_pol_landed_cost_per_unit as subtotal
            from single_pol_landed_cost_per_unit($1) UNION
            select single_pol_landed_cost_per_value as subtotal
            from single_pol_landed_cost_per_value($1)) as result'
            LANGUAGE SQL;
            create or replace view purchase_landed_cost_report as (
                 select
                    min(l.id) as id,
                    s.id as purchase_order_id,
                    s.date_order as date,
                    to_char(s.date_order, 'YYYY') as name,
                    to_char(s.date_order, 'MM') as month,
                    to_char(s.date_order, 'YYYY-MM-DD') as day,
                    s.state,
                    s.date_approve,
                    s.minimum_planned_date as expected_date,
                    s.dest_address_id,
                    s.pricelist_id,
                    s.validator,
                    s.warehouse_id as warehouse_id,
                    s.partner_id as partner_id,
                    s.create_uid as user_id,
                    s.company_id as company_id,
                    l.product_id,
                    t.categ_id as category_id,
                    t.uom_id as product_uom,
                    s.location_id as location_id,
                    sum(l.product_qty/u.factor*u2.factor) as quantity,
                    count(*) as nbr,
                    sum(l.price_unit*l.product_qty)::decimal(16,2)
                    as price_total,
                    avg(100.0 * (l.price_unit*l.product_qty) / NULLIF(
                        t.standard_price*l.product_qty/
                        u.factor*u2.factor, 0.0))::decimal(16,2)
                        as negociation,
                    sum(t.standard_price*l.product_qty/u.factor*u2.factor
                        )::decimal(16,2) as price_standard,
                    (sum(l.product_qty*l.price_unit)/NULLIF(sum(
                        l.product_qty/u.factor*u2.factor),0.0)
                        )::decimal(16,2) as price_average,
                    pol_landed_cost_total(l.id)::decimal(16,2) as
                    landed_cost_total,
                    pol_landed_cost_unit(l.id)::decimal(16,2) as
                    landed_cost_unit
                from purchase_order_line l
                    join purchase_order s on (l.order_id=s.id)
                        left join product_product p on (l.product_id=p.id)
                            left join product_template t on (
                                p.product_tmpl_id=t.id)
                    left join product_uom u on (u.id=l.product_uom)
                    left join product_uom u2 on (u2.id=t.uom_id)
                group by
                    s.company_id,
                    s.create_uid,
                    s.partner_id,
                    u.factor,
                    s.location_id,
                    l.id,
                    s.id,
                    l.price_unit,
                    s.date_approve,
                    l.date_planned,
                    l.product_uom,
                    s.minimum_planned_date,
                    s.pricelist_id,
                    s.validator,
                    s.dest_address_id,
                    l.product_id,
                    t.categ_id,
                    s.date_order,
                    to_char(s.date_order, 'YYYY'),
                    to_char(s.date_order, 'MM'),
                    to_char(s.date_order, 'YYYY-MM-DD'),
                    s.state,
                    s.warehouse_id,
                    u.uom_type,
                    u.category_id,
                    t.uom_id,
                    u.id,
                    u2.factor
            )
        """)
