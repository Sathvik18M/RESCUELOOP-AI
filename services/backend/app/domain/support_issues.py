"""Customer issue vocabulary and safe next steps; never authorizes an operation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SupportIssue:
    code: str
    key: str
    name: str
    example: str
    intent: str
    next_step: str
    review: bool = False


ISSUES = (
    SupportIssue(
        "01",
        "order_confirmation",
        "Order not confirmed",
        "I paid, but my order isn't confirmed.",
        "support",
        "Please share your order reference, or payment reference if no order exists, so the store can reconcile payment and confirmation.",
        True,
    ),
    SupportIssue(
        "02",
        "wrong_order_details",
        "Wrong order details",
        "My order has the wrong product.",
        "support",
        "Please share the order reference and tell us which product you intended to order and which product appears on the order. The store must verify any correction.",
        True,
    ),
    SupportIssue(
        "03",
        "order_cancellation",
        "Order cancellation",
        "I want to cancel my order.",
        "cancellation",
        "Please share your order reference. Cancellation eligibility depends on the verified order and the store's policy; any proposed action needs your confirmation.",
    ),
    SupportIssue(
        "04",
        "order_modification",
        "Order modification",
        "Can I change the size after ordering?",
        "support",
        "Please share the order reference, current size and requested size. The store must check availability and fulfillment before proposing a change.",
        True,
    ),
    SupportIssue(
        "05",
        "duplicate_order",
        "Duplicate order",
        "I accidentally ordered the same item twice.",
        "support",
        "Please share both order references and identify which one you want to keep. The store must verify them before proposing any cancellation or refund.",
        True,
    ),
    SupportIssue(
        "06",
        "delivery_delay",
        "Delayed delivery",
        "My order hasn't arrived yet.",
        "tracking",
        "Please share your order reference so we can check the saved delivery status. A new delivery date cannot be promised without confirmation.",
    ),
    SupportIssue(
        "07",
        "failed_delivery",
        "Failed delivery",
        "The delivery person couldn't find my address.",
        "redelivery",
        "Please share your order reference and the corrected delivery details. A verified failed delivery and your confirmation are required before arranging another attempt.",
    ),
    SupportIssue(
        "08",
        "wrong_address",
        "Wrong delivery address",
        "I entered the wrong address.",
        "support",
        "Please share your order reference and the address correction. The store must check whether the shipment can still be changed.",
        True,
    ),
    SupportIssue(
        "09",
        "missing_package",
        "Missing package",
        "Tracking says delivered, but I haven't received it.",
        "support",
        "Please share your order reference and whether anyone at the delivery address received the package. The store must investigate the delivery discrepancy.",
        True,
    ),
    SupportIssue(
        "10",
        "reschedule_delivery",
        "Reschedule delivery",
        "Can you deliver tomorrow instead?",
        "support",
        "Please share your order reference and preferred delivery date. The store must check availability before confirming a new date.",
        True,
    ),
    SupportIssue(
        "11",
        "store_pickup",
        "Store pickup request",
        "Can I collect my order from your shop?",
        "pickup",
        "Please share your order reference and preferred pickup time. The store must approve availability and you must confirm the pickup terms.",
    ),
    SupportIssue(
        "12",
        "tracking_mismatch",
        "Incorrect delivery status",
        "The tracking information is wrong.",
        "support",
        "Please share your order reference and explain which tracking update is incorrect. The store must verify the discrepancy.",
        True,
    ),
    SupportIssue(
        "13",
        "damaged_product",
        "Damaged product",
        "My headphones arrived broken.",
        "support",
        "Please share your order reference and describe the damage. The store will check evidence and policy before proposing a remedy.",
    ),
    SupportIssue(
        "14",
        "defective_product",
        "Defective product",
        "The device isn't working.",
        "support",
        "Please share your order reference, the product and what happens when you use it. Evidence and eligibility must be checked before proposing a remedy.",
    ),
    SupportIssue(
        "15",
        "wrong_product",
        "Wrong product received",
        "I ordered black but received blue.",
        "support",
        "I'm sorry you received the wrong item. Please share your order reference and describe what you ordered versus what arrived. We must verify the order and evidence before proposing a return or replacement.",
    ),
    SupportIssue(
        "16",
        "missing_items",
        "Missing items",
        "One item is missing from my package.",
        "support",
        "Please share your order reference and list the missing items and what arrived. The store must check the packing and order records.",
        True,
    ),
    SupportIssue(
        "17",
        "poor_quality",
        "Poor product quality",
        "The material quality is bad.",
        "support",
        "Please share your order reference and describe the quality problem. The store must compare the evidence with the published policy before deciding a remedy.",
        True,
    ),
    SupportIssue(
        "18",
        "not_as_described",
        "Product not as described",
        "The product doesn't match the website photos.",
        "support",
        "Please share your order reference and explain how the received product differs from its description. The store must review the listing and evidence.",
        True,
    ),
    SupportIssue(
        "19",
        "return_request",
        "Return request",
        "I want to return this product.",
        "return",
        "Please share your order reference and the reason for returning it. Eligibility, evidence and the published return policy must be checked before you confirm any return.",
    ),
    SupportIssue(
        "20",
        "refund_request",
        "Refund request",
        "I want my money back.",
        "refund",
        "Please share your order reference and refund reason. Refunds depend on verified payment, eligibility, inspection and the store's approval rules.",
    ),
    SupportIssue(
        "21",
        "refund_delayed",
        "Refund delayed",
        "My refund hasn't arrived.",
        "support",
        "Please share your order reference and any refund reference. The store must check the recorded refund status before providing an update or timeframe.",
        True,
    ),
    SupportIssue(
        "22",
        "refund_amount",
        "Refund amount incorrect",
        "I received only ₹500 instead of ₹800.",
        "support",
        "Please share your order or refund reference and the expected and received amounts. The store must reconcile them before considering an adjustment.",
        True,
    ),
    SupportIssue(
        "23",
        "replacement_request",
        "Replacement request",
        "Can you replace my damaged watch?",
        "replacement",
        "Please share your order reference and describe the damage. Replacement eligibility and evidence require review before terms can be offered.",
    ),
    SupportIssue(
        "24",
        "return_pickup",
        "Return pickup problem",
        "Nobody came to collect my return.",
        "support",
        "Please share your order or return reference and the scheduled collection date. The store must check the collection arrangements.",
        True,
    ),
    SupportIssue(
        "25",
        "payment_order_missing",
        "Payment deducted, order missing",
        "Money was deducted, but no order was created.",
        "support",
        "Please share the payment reference, payment date and amount, plus any order reference you received. The store must reconcile the payment before confirming an order or remedy.",
        True,
    ),
    SupportIssue(
        "26",
        "double_payment",
        "Double payment",
        "I was charged twice.",
        "support",
        "Please share your order reference and the two payment references with their amounts. The store must verify a duplicate charge before deciding any adjustment.",
        True,
    ),
    SupportIssue(
        "27",
        "incorrect_charges",
        "Incorrect charges",
        "Why was I charged an extra ₹200?",
        "support",
        "Please share your order reference and identify the unexpected charge. The store must compare the bill with the agreed total.",
        True,
    ),
    SupportIssue(
        "28",
        "invoice",
        "Invoice issue",
        "I need a GST invoice.",
        "support",
        "Please share your order reference and any business billing details needed on the invoice. The store must check the invoice records and issue or correct the document.",
        True,
    ),
    SupportIssue(
        "29",
        "customization_request",
        "Customization request",
        "Can you engrave my name on this wallet?",
        "customization",
        "Please share the order reference and exact engraving text. New customization needs a seller decision and your confirmation of the quoted terms.",
    ),
    SupportIssue(
        "30",
        "wrong_customization",
        "Incorrect customization",
        "You printed the wrong name on my gift.",
        "support",
        "Please share your order reference and the requested text versus the text received. The store must compare the saved customization terms and evidence.",
        True,
    ),
    SupportIssue(
        "31",
        "missing_customization",
        "Missing customization",
        "I paid for gift wrapping, but it wasn't included.",
        "support",
        "Please share your order reference and describe the missing customization. The store must verify the agreed customization and payment records.",
        True,
    ),
    SupportIssue(
        "32",
        "custom_order_delay",
        "Custom order delay",
        "My personalized order isn't ready.",
        "support",
        "Please share your order reference. The store must check the agreed preparation time and current progress before promising a ready date.",
        True,
    ),
    SupportIssue(
        "33",
        "warranty_claim",
        "Warranty claim",
        "My product stopped working during warranty.",
        "warranty",
        "Please share your order reference and describe the fault. The store must check purchase details, warranty coverage and evidence.",
    ),
    SupportIssue(
        "34",
        "unsatisfactory_support",
        "Unsatisfactory support",
        "Your previous solution didn't fix my problem.",
        "unresolved",
        "Please identify the unresolved request or order so we can review the previous solution without counting repeated complaints as new failed solutions.",
    ),
    SupportIssue(
        "35",
        "human_assistance",
        "Human assistance",
        "I want to speak directly with the seller.",
        "handoff",
        "A human support request transfers the conversation to the store team and pauses automated replies.",
    ),
)

BY_CODE = {issue.code: issue for issue in ISSUES}
EVIDENCE_ISSUES = {"13", "14", "15", "17", "18", "30", "31"}


def routing_guide():
    return "\n".join(f"{i.code}: {i.name} -> {i.intent}" for i in ISSUES)


def next_step(issue, provider, order_verified=False):
    text = issue.next_step
    if order_verified:
        text += " The referenced order is verified for this customer; do not ask for its reference again."
    if issue.code in EVIDENCE_ISSUES:
        text += (
            " This WhatsApp test connection cannot retrieve images for AI analysis. Please describe the item in text; the store can review photos manually."
            if provider == "360dialog_sandbox"
            else " You may attach a product photo. Visible evidence can be assessed; unclear evidence needs seller review."
        )
    return text
