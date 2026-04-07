from typing import Any, Callable, Dict, List, Optional, Sequence

from models.customer import Customer
from models.product import Product
from utils.exceptions import ValidationException
from utils.math.financial_calculator import FinancialCalculator
from utils.system.logger import logger


CustomerChooser = Callable[[List[Customer]], Optional[Customer]]


def build_customer_display(customer: Optional[Customer]) -> str:
    """Build a consistent customer display string for sale-related screens."""
    if customer is None:
        return "Cliente eliminado"

    display_parts: List[str] = [customer.identifier_9]
    if customer.identifier_3or4:
        display_parts.append(f"({customer.identifier_3or4})")
    if customer.name:
        display_parts.append(f"- {customer.name}")
    return " ".join(display_parts)


def build_selected_customer_text(customer: Customer) -> str:
    """Build the selected-customer label used in the current sale area."""
    display_parts = []
    if customer.identifier_3or4:
        display_parts.append(customer.identifier_3or4)
    if customer.name:
        display_parts.append(customer.name)
    display_parts.append(customer.identifier_9)
    return " - ".join(display_parts)


def build_customer_selection_text(customer: Customer) -> str:
    """Build a compact customer option label for selection dialogs."""
    display_parts = []
    if customer.identifier_3or4:
        display_parts.append(f"N° Depto: {customer.identifier_3or4}")
    if customer.name:
        display_parts.append(f"Nombre: {customer.name}")
    display_parts.append(f"Tel: {customer.identifier_9}")
    return " | ".join(display_parts)


def build_shortcuts_help_text() -> str:
    """Return the keyboard shortcuts summary used in Sales view."""
    return (
        "Atajos disponibles en Ventas:\n\n"
        "Ctrl+B: Enfocar código de barras\n"
        "Esc: Limpiar venta actual\n"
        "Ctrl+Enter: Finalizar venta\n"
        "F5: Recargar historial de ventas\n"
        "Del: Quitar ítem seleccionado\n"
        "+: Aumentar cantidad del ítem seleccionado\n"
        "-: Disminuir cantidad del ítem seleccionado\n"
        "F1: Mostrar esta ayuda"
    )


def deduplicate_customers_by_phone(
    customers: Sequence[Customer],
) -> List[Customer]:
    """Drop duplicated customer rows that share the same 9-digit identifier."""
    unique_customers: List[Customer] = []
    seen_phones = set()

    for customer in customers:
        if customer.identifier_9 in seen_phones:
            logger.warning(
                "Duplicate customer found for sale selection",
                extra={
                    "identifier_9": customer.identifier_9,
                    "identifier_3or4": customer.identifier_3or4,
                },
            )
            continue

        unique_customers.append(customer)
        seen_phones.add(customer.identifier_9)

    return unique_customers


def resolve_customer_by_identifier(
    identifier: str,
    customer_service: Any,
    chooser: CustomerChooser,
) -> Optional[Customer]:
    """Resolve a customer from the cashier input without changing service contracts."""
    if len(identifier) == 9:
        return customer_service.get_customer_by_identifier_9(identifier)

    if len(identifier) in (3, 4):
        customers = customer_service.get_customers_by_identifier_3or4(identifier)
        logger.debug(
            "Customers found for short identifier",
            extra={"identifier": identifier, "count": len(customers)},
        )
        for customer in customers:
            logger.debug(
                "Customer candidate for sale selection",
                extra={
                    "customer_id": customer.id,
                    "identifier_9": customer.identifier_9,
                    "identifier_3or4": customer.identifier_3or4,
                },
            )

        unique_customers = deduplicate_customers_by_phone(customers)
        if len(unique_customers) == 1:
            return unique_customers[0]
        if len(unique_customers) > 1:
            return chooser(unique_customers)
        return None

    raise ValidationException("Please enter a 3/4-digit or 9-digit identifier")


def build_quick_scan_item_data(product: Product) -> Dict[str, Any]:
    """Build the default sale item payload used by quick-scan mode."""
    quantity = 1.0
    sell_price = int(product.sell_price) if product.sell_price else 0
    cost_price = int(product.cost_price) if product.cost_price else 0
    profit = FinancialCalculator.calculate_item_profit(quantity, sell_price, cost_price)
    return {
        "product_id": product.id,
        "product_name": product.name,
        "quantity": quantity,
        "sell_price": sell_price,
        "profit": profit,
    }


def prepare_processed_sale_items(
    sale_items: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Normalize current sale items before sending them to the service layer."""
    return [
        {
            "product_id": int(item["product_id"]),
            "product_name": str(item["product_name"]),
            "quantity": round(float(item["quantity"]), 3),
            "sell_price": int(item["sell_price"]),
            "profit": int(item["profit"]),
        }
        for item in sale_items
    ]