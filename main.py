// STATUS BACKEND - FIXED VERSION
// Missing /api/payment/create route added
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
require('dotenv').config();

const app = express();

app.use(cors());
app.use(express.json());

// MongoDB Connection
mongoose.connect(process.env.MONGODB_URI)
  .then(() => console.log('✅ MongoDB Connected'))
  .catch(err => console.error('❌ MongoDB Error:', err));

// Couple Schema
const coupleSchema = new mongoose.Schema({
  person1Name: String,
  person2Name: String,
  relationshipDate: Date,
  verified: { type: Boolean, default: false },
  email: String,
  phone: String,
  stripePaymentId: String,
  createdAt: { type: Date, default: Date.now }
});

const Couple = mongoose.model('Couple', coupleSchema);

// ===================================
// ROUTES
// ===================================

// Health Check
app.get('/api/health', (req, res) => {
  res.json({ 
    status: 'healthy', 
    database: mongoose.connection.readyState === 1 ? 'connected' : 'disconnected' 
  });
});

// Search Route
app.get('/api/search', async (req, res) => {
  try {
    const { name } = req.query;
    
    if (!name) {
      return res.status(400).json({ error: 'Name is required' });
    }

    const couples = await Couple.find({
      $or: [
        { person1Name: new RegExp(name, 'i') },
        { person2Name: new RegExp(name, 'i') }
      ]
    }).limit(10);

    res.json({ couples });
  } catch (error) {
    console.error('Search error:', error);
    res.status(500).json({ error: 'Search failed' });
  }
});

// ===================================
// PAYMENT ROUTE - THIS WAS MISSING!
// ===================================
app.post('/api/payment/create', async (req, res) => {
  try {
    const { person1Name, person2Name, relationshipDate, email, phone, amount } = req.body;

    console.log('Payment request received:', { person1Name, person2Name, amount });

    // Create Stripe payment intent
    const paymentIntent = await stripe.paymentIntents.create({
      amount: Math.round(amount * 100), // Convert to cents
      currency: 'usd',
      metadata: {
        person1Name,
        person2Name,
        relationshipDate,
        email
      }
    });

    console.log('Payment intent created:', paymentIntent.id);

    // Save couple to database
    const couple = new Couple({
      person1Name,
      person2Name,
      relationshipDate: new Date(relationshipDate),
      email,
      phone,
      stripePaymentId: paymentIntent.id,
      verified: amount >= 4.99 // Auto-verify if they paid for verified badge
    });

    await couple.save();

    res.json({
      success: true,
      clientSecret: paymentIntent.client_secret,
      coupleId: couple._id
    });

  } catch (error) {
    console.error('Payment creation error:', error);
    res.status(500).json({ 
      error: 'Payment creation failed', 
      message: error.message 
    });
  }
});

// Verify payment (webhook or confirmation)
app.post('/api/payment/confirm', async (req, res) => {
  try {
    const { paymentIntentId } = req.body;

    const paymentIntent = await stripe.paymentIntents.retrieve(paymentIntentId);

    if (paymentIntent.status === 'succeeded') {
      await Couple.findOneAndUpdate(
        { stripePaymentId: paymentIntentId },
        { verified: true }
      );

      res.json({ success: true, message: 'Payment confirmed!' });
    } else {
      res.status(400).json({ error: 'Payment not successful' });
    }
  } catch (error) {
    console.error('Payment confirmation error:', error);
    res.status(500).json({ error: 'Confirmation failed' });
  }
});

// Get couple by ID
app.get('/api/couples/:id', async (req, res) => {
  try {
    const couple = await Couple.findById(req.params.id);
    
    if (!couple) {
      return res.status(404).json({ error: 'Couple not found' });
    }

    res.json({ couple });
  } catch (error) {
    console.error('Get couple error:', error);
    res.status(500).json({ error: 'Failed to get couple' });
  }
});

// Get couple profile (public view)
app.get('/api/couples/:couple_id/profile', async (req, res) => {
  try {
    const couple = await Couple.findById(req.params.couple_id);
    
    if (!couple) {
      return res.status(404).json({ error: 'Couple not found' });
    }

    res.json({
      person1Name: couple.person1Name,
      person2Name: couple.person2Name,
      relationshipDate: couple.relationshipDate,
      verified: couple.verified,
      createdAt: couple.createdAt
    });
  } catch (error) {
    res.status(500).json({ error: 'Profile not found' });
  }
});

// Root route
app.get('/', (req, res) => {
  res.json({ 
    message: 'STATUS API v1.0',
    status: 'running',
    endpoints: [
      'GET /api/health',
      'GET /api/search?name=...',
      'POST /api/payment/create',
      'GET /api/couples/:id'
    ]
  });
});

// Start Server
const PORT = process.env.PORT || 5000;
app.listen(PORT, () => {
  console.log(`✅ STATUS API running on port ${PORT}`);
});

module.exports = app;
