class BaseConverter(object):
    decimal_digits = "0123456789"

    def __init__(self, digits):
        self.digits = digits

    def from_decimal(self, i):
        if i < 0:
            is_negative = True
            i = -i
        else:
            is_negative = False

        result = ""
        while i > 0:
            result = self.digits[i % len(self.digits)] + result
            i //= len(self.digits)
        if is_negative:
            result = "-" + result

        return result or "0"

    def to_decimal(self, s):
        is_negative = s[0] == '-'
        if is_negative:
            s = s[1:]
        decimal = 0
        for digit in s:
            decimal = decimal * len(self.digits) + self.digits.index(digit)
        if is_negative:
            decimal = -decimal
        return decimal

# Create the base62 instance
baseconv = BaseConverter(
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
)

# Monkey patch django.utils
import django.utils
django.utils.baseconv = baseconv 