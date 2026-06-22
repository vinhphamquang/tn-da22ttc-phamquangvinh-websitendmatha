import os
import time
from payos import PayOS
from payos.type import ItemData, PaymentData

# Initialize PayOS using provided credentials
client_id = os.environ.get('PAYOS_CLIENT_ID', '49142e2e-6a87-4e37-85bb-0a18e404c0c3')
api_key = os.environ.get('PAYOS_API_KEY', '07268295-4829-4a53-abbc-0ed728e6fac7')
checksum_key = os.environ.get('PAYOS_CHECKSUM_KEY', '9787b8538149f1879c21d86717c209b1621349eac49f89401ee2f54689296ed7')

payos_client = PayOS(client_id=client_id, api_key=api_key, checksum_key=checksum_key)

PREMIUM_PRICE = 2000  # 2.000 VNĐ

def generate_order_id(user_id):
    """
    Generate numeric order ID for PayOS.
    PayOS requires integer <= 9007199254740991.
    We use timestamp in milliseconds and a small padding.
    """
    timestamp = int(time.time() * 1000)
    # 13 digits for timestamp. user_id up to 2 digits.
    # Total ~15 digits, safe within limits.
    # But wait, to be safe and simple, let's just use timestamp.
    # We will track `user_id` by finding the order in database.
    return int(timestamp)

def create_payos_payment(order_id, amount, description, return_url, cancel_url):
    """
    Create PayOS payment link
    """
    try:
        # Construct item data
        item = ItemData(name="Gói Premium", quantity=1, price=amount)
        
        # Payment Data
        payment_data = PaymentData(
            orderCode=int(order_id),
            amount=int(amount),
            description=description[:25], # Description max 25 chars for PayOS
            items=[item],
            cancelUrl=cancel_url,
            returnUrl=return_url
        )
        
        print(f"[PAYOS] Creating payment: orderCode={order_id}, amount={amount}")
        
        # Create payment link
        payment_link = payos_client.createPaymentLink(paymentData=payment_data)
        
        return {
            'success': True,
            'checkoutUrl': payment_link.checkoutUrl,
            'orderId': str(order_id),
            'message': 'Tạo đơn thanh toán thành công'
        }
    except Exception as e:
        print(f"[PAYOS ERROR] {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'message': f'Lỗi kết nối PayOS: {str(e)}'
        }

def verify_payos_webhook(webhook_body):
    """
    Verify signature of PayOS webhook callback
    """
    try:
        # verifyPaymentWebhookData returns the webhook data if valid
        webhook_data = payos_client.verifyPaymentWebhookData(webhook_body)
        print(f"[PAYOS VERIFY] Valid webhook for orderCode={webhook_data.orderCode}")
        return True, webhook_data
    except Exception as e:
        print(f"[PAYOS VERIFY ERROR] {e}")
        return False, None
