class Product:
    def __init__(self, id, name, description):
        self.id = id
        self.name = name
        self.description = description

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row['id'],
            name=row['name'],
            description=row['description']
        )