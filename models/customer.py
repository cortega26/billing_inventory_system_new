class Customer:
    def __init__(self, id, identifier_9, identifier_4=None):
        self.id = id
        self.identifier_9 = identifier_9
        self.identifier_4 = identifier_4

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            identifier_9=row['identifier_9'],
            identifier_4=row['identifier_4']
        )