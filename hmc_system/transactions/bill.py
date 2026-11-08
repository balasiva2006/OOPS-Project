"""Bill totals and outstanding balance; amounts are integer paise."""
from dataclasses import dataclass

@dataclass
class Bill:
    id: int
    rent: int
    mess: int
    amenity: int
    paid: int

    @property
    def total(self):
        return self.rent + self.mess + self.amenity

    @property
    def balance(self):
        return self.total - self.paid
