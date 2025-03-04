def generate_upi_payment_url(amount):
    upi_id = "7678023772@fam"  # Replace with your actual UPI ID
    payee_name = "Print Service"
    currency = "INR"
    return f"upi://pay?pa={upi_id}&pn={payee_name}&am={amount}&cu={currency}"