from models.customer import Customer


class TestCustomerCreditColumns:
    def test_credit_column_defaults(self):
        customer = Customer(identifier_9="912345678")
        assert customer.current_balance == 0
        assert customer.credit_limit == 50000

    def test_credit_column_values_round_trip(self):
        customer = Customer(
            identifier_9="912345678",
            current_balance=1200,
            credit_limit=100000,
        )
        assert customer.current_balance == 1200
        assert customer.credit_limit == 100000
