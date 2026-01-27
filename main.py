# Add this to your server.py file in the status-backend repository

# NEW ENDPOINT: Create verified badge payment session
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
                        'description': 'Premium verified badge with photo upload',
                    },
                    'unit_amount': 499,  # $4.99
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f'{FRONTEND_URL}?verified=true&couple_id={couple_id}',
            cancel_url=FRONTEND_URL,
            metadata={
                'couple_id': couple_id,
                'type': 'verified_badge'
            }
        )
        return jsonify({'url': checkout_session.url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# UPDATE: Modify the webhook to handle verified badge payments
# In your existing webhook handler, add this case:

# Inside the checkout.session.completed handler:
"""
if event['type'] == 'checkout.session.completed':
    session = event['data']['object']
    metadata = session.get('metadata', {})
    
    # Check if this is a verified badge upgrade
    if metadata.get('type') == 'verified_badge':
        couple_id = metadata.get('couple_id')
        if couple_id:
            # Update the couple to be verified
            couples_collection.update_one(
                {'_id': ObjectId(couple_id)},
                {'$set': {'verified': True, 'verified_at': datetime.utcnow()}}
            )
"""
