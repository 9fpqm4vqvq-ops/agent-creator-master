"""Illustrative unit economics per attempted order; inputs are never market facts."""
import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def unit_economics(assumptions):
    required = ('sale_price', 'unit_cost', 'outbound_shipping', 'return_shipping',
                'packaging', 'ad_cost_per_attempt', 'cancellation_rate',
                'delivery_success_rate', 'return_rate', 'cod_fee_rate',
                'inventory_recovery_rate', 'fixed_monthly_cost')
    if not isinstance(assumptions, dict) or any(k not in assumptions for k in required):
        raise ValueError('Every cost and probability assumption must be supplied explicitly')
    values = {}
    for key in required:
        try:
            value = Decimal(str(assumptions[key]))
        except (InvalidOperation, ValueError):
            raise ValueError('Invalid numeric assumption: ' + key) from None
        if not value.is_finite() or value < 0:
            raise ValueError('Costs/rates must be finite and nonnegative')
        if key.endswith('_rate') and value > 1:
            raise ValueError('Probabilities/fee rates must be within 0..1')
        values[key] = value
    a = values
    shipped = 1 - a['cancellation_rate']
    delivered = shipped * a['delivery_success_rate']
    returns = delivered * a['return_rate']
    failed = shipped - delivered
    retained = delivered - returns
    revenue = retained * a['sale_price']
    goods = shipped * a['unit_cost'] - (failed + returns) * a['unit_cost'] * a['inventory_recovery_rate']
    expenses = {'goods_net_of_modeled_recovery': goods,
        'outbound_shipping': shipped * a['outbound_shipping'],
        'return_shipping': (failed + returns) * a['return_shipping'],
        'packaging': shipped * a['packaging'],
        'advertising': a['ad_cost_per_attempt'],
        # Explicit conservative convention: fee charged on delivered value, including returns.
        'cod_fees': delivered * a['sale_price'] * a['cod_fee_rate']}
    contribution = revenue - sum(expenses.values())
    money = lambda x: str(x.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    return {'classification': 'ESTIMATE', 'basis': 'per attempted order',
        'currency': assumptions.get('currency', 'UNSPECIFIED'),
        'assumptions': {k: str(v) for k, v in a.items()},
        'expected_retained_sales_per_attempt': str(retained),
        'expected_revenue': money(revenue), 'expected_costs': {k: money(v) for k, v in expenses.items()},
        'expected_contribution': money(contribution),
        'monthly_breakeven_attempts': math.ceil(a['fixed_monthly_cost'] / contribution) if contribution > 0 else None,
        'limitations': ['Modeled estimates only; validate all prices, rates and service terms independently.',
            'Inventory recovery assumes returned units can be reused at the given fraction; verify this.',
            'COD fees are modeled on delivered value including later returns.',
            'Taxes, customs, settlement delays, stock financing and one-time setup costs need separate verified inputs.']}
