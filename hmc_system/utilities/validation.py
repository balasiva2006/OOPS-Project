"""Validate money and billing months; provide consistent UTC timestamps."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount < 0 or amount > 10000000 or amount != amount.quantize(Decimal('.01')):
            raise ValueError
        return int(amount * 100)
    except (InvalidOperation, ValueError, OverflowError):
        raise ValueError('Enter a non-negative amount with at most two decimal places.')

def month_value(value):
    if not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', value or '') or not 2000 <= int(value[:4]) <= 2100:
        raise ValueError('Choose a valid month between 2000 and 2100.')
    return value
