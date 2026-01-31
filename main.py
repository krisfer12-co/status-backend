import { useState, useEffect } from 'react'
import './App.css'

const API_URL = 'https://status-api-8f7v.onrender.com/api'

function App() {
  const [view, setView] = useState<'home' | 'search' | 'register' | 'profile' | 'delete' | 'upgrade'>('home')
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [hasPaid, setHasPaid] = useState(false)
  const [selectedCouple, setSelectedCouple] = useState<any>(null)
  const [apiReady, setApiReady] = useState(false)
  const [newCoupleId, setNewCoupleId] = useState<string | null>(null)
  const [showUpgradeOffer, setShowUpgradeOffer] = useState(false)
  
  const [formData, setFormData] = useState({ name: '', email: '', phone: '', city: '', state: '', age: '' })
  const [partnerData, setPartnerData] = useState({ name: '', email: '', phone: '', city: '', state: '', age: '' })
  const [anniversaryDate, setAnniversaryDate] = useState('')
  
  const [deleteEmail, setDeleteEmail] = useState('')
  const [deleteStep, setDeleteStep] = useState(1)
  const [deleteConfirm, setDeleteConfirm] = useState('')

  // Wake up API on page load
  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then(() => setApiReady(true))
      .catch(() => {
        // Retry after 2 seconds if first attempt fails
        setTimeout(() => {
          fetch(`${API_URL}/health`).then(() => setApiReady(true)).catch(() => {})
        }, 2000)
      })
  }, [])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    if (params.get('paid') === 'true') {
      setHasPaid(true)
      setView('register')
      setStep(1)
      setSuccess('Payment successful! Complete your registration.')
      window.history.replaceState({}, '', '/')
    }
    // Handle verified badge upgrade return
    if (params.get('verified') === 'true') {
      setSuccess('🎉 Verified Badge activated! Your profile is now premium.')
      window.history.replaceState({}, '', '/')
    }
  }, [])

  const handleSearch = async () => {
    if (!searchQuery.trim()) return
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/search?name=${encodeURIComponent(searchQuery)}`)
      const data = await response.json()
      setSearchResults(data.results || [])
    } catch { setError('Search failed') }
    setLoading(false)
  }

  const viewProfile = (couple: any) => {
    setSelectedCouple(couple)
    setView('profile')
  }

  const startRegistration = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/payment/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      })
      const data = await response.json()
      if (data.url) {
        window.location.href = data.url
      } else {
        setError('Payment not available')
      }
    } catch { setError('Payment failed') }
    setLoading(false)
  }

  const formatDate = (dateString: string) => {
    if (!dateString) return ''
    const date = new Date(dateString)
    return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
  }

  const completeRegistration = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/couples`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          person1: formData, 
          person2: partnerData,
          anniversary: anniversaryDate
        })
      })
      const data = await response.json()
      if (data.couple_id) {
        setNewCoupleId(data.couple_id)
        setSuccess(`Congratulations! ${formData.name} & ${partnerData.name} are now registered!`)
        // Show upgrade offer instead of going home
        setTimeout(() => {
          setShowUpgradeOffer(true)
        }, 2000)
      } else {
        setError(data.error || 'Registration failed')
      }
    } catch { setError('Registration failed') }
    setLoading(false)
  }

  const startVerifiedUpgrade = async () => {
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/payment/create-verified`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ couple_id: newCoupleId })
      })
      const data = await response.json()
      if (data.url) {
        window.location.href = data.url
      } else {
        setError('Payment not available')
      }
    } catch { setError('Upgrade payment failed') }
    setLoading(false)
  }

  const skipUpgrade = () => {
    setShowUpgradeOffer(false)
    setView('home')
    setStep(1)
    setHasPaid(false)
    setNewCoupleId(null)
    setFormData({ name: '', email: '', phone: '', city: '', state: '', age: '' })
    setPartnerData({ name: '', email: '', phone: '', city: '', state: '', age: '' })
    setAnniversaryDate('')
  }

  const requestDelete = async () => {
    if (!deleteEmail.trim()) {
      setError('Please enter your email')
      return
    }
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/delete/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: deleteEmail })
      })
      const data = await response.json()
      if (data.success) {
        setDeleteStep(2)
      } else {
        setError(data.error || 'Could not find registration with this email')
      }
    } catch { setError('Request failed') }
    setLoading(false)
  }

  const confirmDelete = async () => {
    if (deleteConfirm !== 'DELETE') {
      setError('Please type DELETE to confirm')
      return
    }
    setLoading(true)
    try {
      const response = await fetch(`${API_URL}/delete/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: deleteEmail })
      })
      const data = await response.json()
      if (data.success) {
        setSuccess('Your registration has been deleted')
        setDeleteEmail('')
        setDeleteConfirm('')
        setDeleteStep(1)
        setTimeout(() => setView('home'), 3000)
      } else {
        setError(data.error || 'Could not delete registration')
      }
    } catch { setError('Delete failed') }
    setLoading(false)
  }

  const canProceed = () => {
    if (step === 1) return formData.name && formData.email && formData.phone && formData.city && formData.state && formData.age
    if (step === 2) return partnerData.name && partnerData.email && partnerData.phone && partnerData.city && partnerData.state && partnerData.age
    if (step === 3) return anniversaryDate
    return false
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="premium-header">
        <div className="logo-section">
          <div className="logo-mark">S</div>
          <div className="logo-text">
            <h1>STATUS</h1>
            <span className="logo-tagline">RELATIONSHIP REGISTRY</span>
          </div>
        </div>
        <nav className="nav-tabs">
          <button className={`nav-tab ${view === 'home' ? 'active' : ''}`} onClick={() => setView('home')}>
            <span className="tab-icon">🏠</span>
            <span>Home</span>
          </button>
          <button className={`nav-tab ${view === 'search' ? 'active' : ''}`} onClick={() => setView('search')}>
            <span className="tab-icon">🔍</span>
            <span>Search</span>
          </button>
          <button className={`nav-tab ${view === 'register' ? 'active' : ''}`} onClick={() => hasPaid ? setView('register') : startRegistration()}>
            <span className="tab-icon">💍</span>
            <span>Register</span>
          </button>
        </nav>
      </header>

      {error && <div className="alert error">{error}<button onClick={() => setError('')}>✕</button></div>}
      {success && <div className="alert success">{success}<button onClick={() => setSuccess('')}>✕</button></div>}

      {view === 'home' && (
        <>
          {/* Hero Section */}
          <section className="hero-section">
            <div className="hero-badge">✨ THE OFFICIAL RELATIONSHIP REGISTRY</div>
            <h1 className="hero-title">
              Is Someone Already<br/><span className="gradient-text">Taken?</span>
            </h1>
            <p className="hero-subtitle">
              Find out instantly. Or register your relationship and show the world you're officially off the market.
            </p>
            <p className="hero-tagline">"Because trust shouldn't be a guessing game."</p>
            
            <div className="hero-buttons">
              <button className="btn-primary" onClick={startRegistration} disabled={loading}>
                {loading ? 'Loading...' : 'Register Your Relationship'}
                <span className="btn-price">$0.99</span>
              </button>
              <button className="btn-secondary" onClick={() => setView('search')}>
                <span className="btn-icon">🔍</span>
                Search Someone Free
              </button>
            </div>
            
            <div className="trust-badges">
              <div className="trust-item">🔒 Secure & Private</div>
              <div className="trust-item">⚡ Instant Results</div>
              <div className="trust-item">💳 Powered by Stripe</div>
            </div>
          </section>

          {/* How It Works - GREEN SECTION */}
          <section className="section green-section">
            <div className="section-header">
              <span className="section-badge">Simple Process</span>
              <h2 className="section-title">How It Works</h2>
              <p className="section-subtitle">Three easy steps to make your relationship official</p>
            </div>
            
            <div className="steps-grid" style={{maxWidth: '1100px', margin: '0 auto'}}>
              <div className="step-card blue-card">
                <div className="step-number">01</div>
                <div className="step-icon">💳</div>
                <h3>Quick Checkout</h3>
                <p>One-time payment of $0.99. No subscriptions, no hidden fees, no surprises.</p>
              </div>
              <div className="step-card green-card">
                <div className="step-number">02</div>
                <div className="step-icon">📝</div>
                <h3>Enter Details</h3>
                <p>Provide your information and your partner's details. Takes less than 2 minutes.</p>
              </div>
              <div className="step-card blue-card">
                <div className="step-number">03</div>
                <div className="step-icon">✅</div>
                <h3>You're Official</h3>
                <p>Your relationship is now verified and searchable on STATUS.</p>
              </div>
            </div>
          </section>

          {/* Benefits Section - BLUE SECTION */}
          <section className="section blue-section">
            <div className="section-header">
              <span className="section-badge">Why STATUS?</span>
              <h2 className="section-title">The Modern Way to Declare Your Love</h2>
            </div>
            
            <div className="benefits-grid" style={{maxWidth: '1100px', margin: '0 auto'}}>
              <div className="benefit-card green-card">
                <div className="benefit-icon">🛡️</div>
                <h3>Protect Your Relationship</h3>
                <p>Let others know your partner is taken before they even try to make a move.</p>
              </div>
              <div className="benefit-card blue-card">
                <div className="benefit-icon">🔍</div>
                <h3>Instant Verification</h3>
                <p>Anyone can search to verify if someone is in a registered relationship.</p>
              </div>
              <div className="benefit-card blue-card">
                <div className="benefit-icon">💝</div>
                <h3>Celebrate Your Bond</h3>
                <p>Commemorate your anniversary and share your love story with the world.</p>
              </div>
              <div className="benefit-card green-card">
                <div className="benefit-icon">🌍</div>
                <h3>Public Declaration</h3>
                <p>A modern way to show commitment in the digital age.</p>
              </div>
            </div>
          </section>

          {/* Social Proof */}
          <section className="section testimonial-section">
            <div className="testimonial-card">
              <div className="quote-mark">"</div>
              <p className="testimonial-text">Finally, a simple way to show we're serious about each other. Now there's no confusion!</p>
              <div className="testimonial-author">
                <div className="author-avatar">💑</div>
                <div className="author-info">
                  <strong>Happy Couple</strong>
                  <span>Registered on STATUS</span>
                </div>
              </div>
            </div>
          </section>

          {/* FAQ Section */}
          <section className="section faq-section">
            <div className="section-header">
              <span className="section-badge">Got Questions?</span>
              <h2 className="section-title">Frequently Asked Questions</h2>
            </div>
            
            <div className="faq-grid">
              <div className="faq-card">
                <h4>Is this legally binding?</h4>
                <p>No, STATUS is a fun way to publicly declare your relationship. It's about making a statement to the world that you're committed to each other!</p>
              </div>
              <div className="faq-card">
                <h4>Can I remove my registration?</h4>
                <p>Yes, you can delete your registration anytime. We understand relationships can change.</p>
              </div>
              <div className="faq-card">
                <h4>Is my information safe?</h4>
                <p>Names and city are public (that's the point!). Email and phone stay private - only used for account management.</p>
              </div>
              <div className="faq-card">
                <h4>Why $0.99?</h4>
                <p>The small fee prevents spam and helps maintain the platform. One-time only, no recurring charges ever.</p>
              </div>
            </div>
          </section>

          {/* Final CTA */}
          <section className="section cta-section">
            <div className="cta-card">
              <h2>Ready to Make It <span className="gradient-text">Official?</span></h2>
              <p>Join couples who are proudly declaring their relationship status.</p>
              <button className="btn-primary btn-large" onClick={startRegistration} disabled={loading}>
                {loading ? 'Loading...' : 'Get Started Now'}
                <span className="btn-arrow">→</span>
              </button>
              <span className="cta-note">🔒 Secure checkout • Only $0.99 • Takes 2 minutes</span>
            </div>
          </section>

          {/* Footer Link */}
          <div className="footer-link">
            <button className="link-button" onClick={() => { setView('delete'); setDeleteStep(1); setDeleteEmail(''); setDeleteConfirm(''); }}>
              Need to delete your registration?
            </button>
          </div>
        </>
      )}

      {view === 'search' && (
        <div className="page-card">
          <div className="card-header">
            <span className="card-icon">🔍</span>
            <h2>Search Someone</h2>
            <p>Check if someone is in a registered relationship</p>
          </div>
          <div className="search-box">
            <input 
              type="text" 
              placeholder="Enter their name..." 
              value={searchQuery} 
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            />
            <button className="btn-primary" onClick={handleSearch} disabled={loading}>
              {loading ? 'Searching...' : 'Search'}
            </button>
          </div>
          
          {searchResults.length > 0 ? (
            <div className="results-list">
              {searchResults.map((r, i) => (
                <div key={i} className="result-card" onClick={() => viewProfile(r)}>
                  <div className="result-avatar">💑</div>
                  <div className="result-info">
                    <strong>{r.person1?.name} & {r.person2?.name}</strong>
                    <span>📍 {r.person1?.city}, {r.person1?.state}</span>
                  </div>
                  <div className="result-action">View →</div>
                </div>
              ))}
            </div>
          ) : searchQuery && !loading ? (
            <div className="no-results">
              <span className="no-results-icon">🔍</span>
              <p>No results found for "{searchQuery}"</p>
              <span>They might not be registered yet!</span>
            </div>
          ) : null}
          
          <button className="btn-back" onClick={() => setView('home')}>← Back to Home</button>
        </div>
      )}

      {view === 'profile' && selectedCouple && (
        <div className="page-card profile-card">
          <button className="btn-back" onClick={() => setView('search')}>← Back to Search</button>
          
          <div className="profile-header">
            <div className="profile-avatar">💑</div>
            <div className="profile-status">✓ VERIFIED COUPLE</div>
            <h2>{selectedCouple.person1?.name} & {selectedCouple.person2?.name}</h2>
            {selectedCouple.anniversary && (
              <p className="profile-anniversary">💚 Together since {formatDate(selectedCouple.anniversary)}</p>
            )}
          </div>
          
          <div className="profile-grid">
            <div className="profile-person-card">
              <span className="person-label">Partner 1</span>
              <h3>{selectedCouple.person1?.name}</h3>
              <p>📍 {selectedCouple.person1?.city}, {selectedCouple.person1?.state}</p>
            </div>
            <div className="profile-person-card">
              <span className="person-label">Partner 2</span>
              <h3>{selectedCouple.person2?.name}</h3>
              <p>📍 {selectedCouple.person2?.city}, {selectedCouple.person2?.state}</p>
            </div>
          </div>
          
          <div className="profile-badge">
            <span>🛡️ Verified on STATUS Registry</span>
          </div>
        </div>
      )}

      {view === 'delete' && (
        <div className="page-card">
          <button className="btn-back" onClick={() => setView('home')}>← Back to Home</button>
          
          <div className="card-header">
            <span className="card-icon">🗑️</span>
            <h2>Delete Registration</h2>
          </div>
          
          {deleteStep === 1 && (
            <>
              <p className="card-description">Enter the email you used to register</p>
              <input 
                type="email" 
                placeholder="your@email.com" 
                value={deleteEmail} 
                onChange={(e) => setDeleteEmail(e.target.value)} 
              />
              <button className="btn-danger" onClick={requestDelete} disabled={loading}>
                {loading ? 'Checking...' : 'Find My Registration'}
              </button>
            </>
          )}
          
          {deleteStep === 2 && (
            <>
              <div className="warning-box">
                <span>⚠️</span>
                <p><strong>Warning:</strong> This cannot be undone!</p>
              </div>
              <p className="card-description">Type DELETE to confirm removal</p>
              <input 
                type="text" 
                placeholder="Type DELETE" 
                value={deleteConfirm} 
                onChange={(e) => setDeleteConfirm(e.target.value.toUpperCase())} 
              />
              <button className="btn-danger" onClick={confirmDelete} disabled={loading || deleteConfirm !== 'DELETE'}>
                {loading ? 'Deleting...' : 'Permanently Delete'}
              </button>
              <button className="btn-secondary" onClick={() => { setDeleteStep(1); setDeleteConfirm(''); }}>
                Cancel
              </button>
            </>
          )}
          
          <p className="note">Note: Payments are non-refundable</p>
        </div>
      )}

      {view === 'register' && hasPaid && (
        <div className="page-card register-card">
          <div className="progress-bar">
            <div className="progress-fill" style={{width: `${(step / 3) * 100}%`}}></div>
          </div>
          <div className="step-indicators">
            {[1, 2, 3].map(s => (
              <div key={s} className={`step-dot ${s <= step ? 'active' : ''} ${s === step ? 'current' : ''}`}>
                {s < step ? '✓' : s}
              </div>
            ))}
          </div>
          
          {step === 1 && (
            <>
              <div className="card-header">
                <span className="card-icon">👤</span>
                <h2>Your Information</h2>
                <p>Tell us about yourself</p>
              </div>
              <div className="form-grid">
                <input type="text" placeholder="Your Full Name" value={formData.name} onChange={(e) => setFormData({...formData, name: e.target.value})} />
                <input type="email" placeholder="Your Email" value={formData.email} onChange={(e) => setFormData({...formData, email: e.target.value})} />
                <input type="tel" placeholder="Your Phone" value={formData.phone} onChange={(e) => setFormData({...formData, phone: e.target.value})} />
                <input type="text" placeholder="Your City" value={formData.city} onChange={(e) => setFormData({...formData, city: e.target.value})} />
                <input type="text" placeholder="Your State" value={formData.state} onChange={(e) => setFormData({...formData, state: e.target.value})} />
                <input type="number" placeholder="Your Age" value={formData.age} onChange={(e) => setFormData({...formData, age: e.target.value})} />
              </div>
            </>
          )}
          
          {step === 2 && (
            <>
              <div className="card-header">
                <span className="card-icon">💕</span>
                <h2>Partner's Information</h2>
                <p>Tell us about your partner</p>
              </div>
              <div className="form-grid">
                <input type="text" placeholder="Partner's Full Name" value={partnerData.name} onChange={(e) => setPartnerData({...partnerData, name: e.target.value})} />
                <input type="email" placeholder="Partner's Email" value={partnerData.email} onChange={(e) => setPartnerData({...partnerData, email: e.target.value})} />
                <input type="tel" placeholder="Partner's Phone" value={partnerData.phone} onChange={(e) => setPartnerData({...partnerData, phone: e.target.value})} />
                <input type="text" placeholder="Partner's City" value={partnerData.city} onChange={(e) => setPartnerData({...partnerData, city: e.target.value})} />
                <input type="text" placeholder="Partner's State" value={partnerData.state} onChange={(e) => setPartnerData({...partnerData, state: e.target.value})} />
                <input type="number" placeholder="Partner's Age" value={partnerData.age} onChange={(e) => setPartnerData({...partnerData, age: e.target.value})} />
              </div>
            </>
          )}
          
          {step === 3 && (
            <>
              <div className="card-header">
                <span className="card-icon">📅</span>
                <h2>Your Anniversary</h2>
                <p>When did your love story begin?</p>
              </div>
              <input 
                type="date" 
                value={anniversaryDate} 
                onChange={(e) => setAnniversaryDate(e.target.value)} 
                className="date-input"
              />
              {anniversaryDate && (
                <div className="anniversary-preview">
                  💚 Together since {formatDate(anniversaryDate)}
                </div>
              )}
            </>
          )}
          
          <div className="form-actions">
            {step > 1 && <button className="btn-secondary" onClick={() => setStep(step - 1)}>← Back</button>}
            {step < 3 ? (
              <button className="btn-primary" onClick={() => setStep(step + 1)} disabled={!canProceed()}>
                Continue →
              </button>
            ) : (
              <button className="btn-primary btn-success" onClick={completeRegistration} disabled={!canProceed() || loading}>
                {loading ? 'Registering...' : '✓ Complete Registration'}
              </button>
            )}
          </div>
        </div>
      )}

      {view === 'register' && !hasPaid && (
        <div className="page-card">
          <div className="card-header">
            <span className="card-icon">💍</span>
            <h2>Register Your Relationship</h2>
            <p>One-time fee to make it official</p>
          </div>
          <div className="price-display">
            <span className="price">$0.99</span>
            <span className="price-note">one-time payment</span>
          </div>
          <button className="btn-primary btn-large" onClick={startRegistration} disabled={loading}>
            {loading ? 'Loading...' : 'Continue to Payment →'}
          </button>
          <div className="payment-badges">
            <span>🔒 Secure</span>
            <span>💳 Stripe</span>
            <span>✓ Instant</span>
          </div>
        </div>
      )}

      {/* Upgrade Offer Modal */}
      {showUpgradeOffer && (
        <div className="upgrade-overlay">
          <div className="upgrade-modal">
            <div className="upgrade-badge">🎉 SPECIAL OFFER</div>
            <h2>Get the <span className="gradient-text">Verified Badge!</span></h2>
            <p className="upgrade-subtitle">Stand out and show you're serious about your relationship</p>
            
            <div className="upgrade-features">
              <div className="upgrade-feature">
                <span className="feature-icon">✨</span>
                <div>
                  <strong>Verified Badge</strong>
                  <p>Gold checkmark on your profile</p>
                </div>
              </div>
              <div className="upgrade-feature">
                <span className="feature-icon">📸</span>
                <div>
                  <strong>Couple Photo</strong>
                  <p>Upload your photo to your profile</p>
                </div>
              </div>
              <div className="upgrade-feature">
                <span className="feature-icon">⭐</span>
                <div>
                  <strong>Priority Listing</strong>
                  <p>Appear first in search results</p>
                </div>
              </div>
              <div className="upgrade-feature">
                <span className="feature-icon">💎</span>
                <div>
                  <strong>Premium Profile</strong>
                  <p>Enhanced profile design</p>
                </div>
              </div>
            </div>
            
            <div className="upgrade-price">
              <span className="upgrade-amount">$4.99</span>
              <span className="upgrade-note">one-time • lifetime access</span>
            </div>
            
            <button className="btn-primary btn-upgrade" onClick={startVerifiedUpgrade} disabled={loading}>
              {loading ? 'Loading...' : '✨ Get Verified Badge'}
            </button>
            
            <button className="btn-skip" onClick={skipUpgrade}>
              No thanks, I'll skip for now
            </button>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="premium-footer">
        <div className="footer-content">
          <div className="footer-brand">
            <div className="footer-logo">S</div>
            <span>STATUS</span>
          </div>
          <p>© 2026 STATUS Registry. Made with 💚 for couples everywhere.</p>
          <p className="fine-print">STATUS is a social declaration service and is not a legal document. Registration does not constitute a legal marriage, civil union, or any legally binding agreement. For legal matters regarding relationships, please consult appropriate legal counsel in your jurisdiction.</p>
        </div>
      </footer>
    </div>
  )
}

export default App
