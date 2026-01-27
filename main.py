@app.route('/api/payment/create-verified', methods=['POST'])
def create_verified_payment():
    try:
        data = request.get_json() or {}
        couple_id = data.get('couple_id')
        
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'STATUS - Verified Badge',
                    },
                    'unit_amount': 499,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f'{FRONTEND_URL}?verified=true',
            cancel_url=FRONTEND_URL,
        )
        return jsonify({'url': checkout_session.url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
