import { useState, useEffect, useRef } from 'react';
import './index.css';

function App() {
  const [stats, setStats] = useState({
    total_events: 0,
    processed_events: 0,
    recovered_count: 0,
    total_recovered_amount: 0,
    recovery_rate_percent: 0,
    total_potential_loss: 0
  });
  const [loadingStats, setLoadingStats] = useState(true);

  const fetchStats = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/dashboard/stats');
      const data = await res.json();
      setStats(data);
      setLoadingStats(false);
    } catch (e) {
      console.error(e);
      setLoadingStats(false);
    }
  };

  const [processedEvents, setProcessedEvents] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [intervalId, setIntervalId] = useState(null);

  // Copilot States
  const [chatHistory, setChatHistory] = useState([
    { role: 'assistant', content: 'Hello! I am your Aegis AI Merchant Copilot. I can query failed transactions, show your recovery statistics, or help you manually generate recovery discounts. How can I help you today?' }
  ]);
  const [inputValue, setInputValue] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef(null);

// fetchStats is defined earlier with loading handling
  const fetchProcessed = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/dashboard/processed');
      const data = await res.json();
      setProcessedEvents(data);
    } catch (e) {
      console.error(e);
    }
  };

  const processNext = async () => {
    try {
      await fetch('http://localhost:8000/api/engine/process_next', { method: 'POST' });
      fetchStats();
      fetchProcessed();
    } catch (e) {
      console.error(e);
    }
  };

  const processBatch = async () => {
    try {
      await fetch('http://localhost:8000/api/engine/process_batch?count=10', { method: 'POST' });
      fetchStats();
      fetchProcessed();
    } catch (e) {
      console.error(e);
    }
  };

  const resetEngine = async () => {
    try {
      await fetch('http://localhost:8000/api/engine/reset', { method: 'POST' });
      fetchStats();
      fetchProcessed();
    } catch (e) {
      console.error(e);
    }
  };

  const toggleAutoProcess = () => {
    if (isProcessing) {
      clearInterval(intervalId);
      setIntervalId(null);
      setIsProcessing(false);
    } else {
      const id = setInterval(processNext, 2000);
      setIntervalId(id);
      setIsProcessing(true);
    }
  };

  const sendChatMessage = async (e, textOverride = null) => {
    if (e) e.preventDefault();
    const textToSend = textOverride || inputValue;
    if (!textToSend.trim() || chatLoading) return;

    const userMessage = { role: 'user', content: textToSend };
    setChatHistory(prev => [...prev, userMessage]);
    if (!textOverride) setInputValue("");
    setChatLoading(true);

    try {
      const res = await fetch('http://localhost:8000/api/copilot/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          history: [...chatHistory, userMessage]
        })
      });

      const data = await res.json();
      setChatHistory(prev => [...prev, { role: 'assistant', content: data.reply }]);

      // Auto refresh stats and feed
      fetchStats();
      fetchProcessed();
    } catch (err) {
      console.error(err);
      setChatHistory(prev => [...prev, { role: 'assistant', content: '⚠️ Failed to connect to Copilot service. Please ensure the backend is running.' }]);
    } finally {
      setChatLoading(false);
    }
  };

  const triggerQuickAction = (text) => {
    sendChatMessage(null, text);
  };

  useEffect(() => {
    fetchStats();
    fetchProcessed();

    // Polling stats every 4 seconds to capture mock checkout conversions
    const pollId = setInterval(() => {
      fetchStats();
      fetchProcessed();
    }, 4000);

    return () => {
      if (intervalId) clearInterval(intervalId);
      clearInterval(pollId);
    };
  }, [intervalId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory]);

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(amount);
  };

  const formatType = (type) => {
    return type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  };

  const extractAndRenderPayLink = (actionText) => {
    if (!actionText) return null;
    const match = actionText.match(/(https?:\/\/localhost:8000\/pay\/[a-zA-Z0-9_]+)/);
    if (match) {
      return (
        <div style={{ marginTop: '0.5rem' }}>
          <a href={match[0]} target="_blank" rel="noopener noreferrer" className="recovery-link-btn">
            ⚡ Open Checkout (Simulate Customer Click)
          </a>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="dashboard-container">
      <header>
        <div className="logo-area">
          <h1>Aegis AI</h1>
          <p>Autonomous Revenue Recovery Control Center</p>
        </div>
        <div className="flex gap-4">
          <button className="btn" onClick={resetEngine}>Reset Simulator</button>
          <button className={`btn ${isProcessing ? 'danger' : 'primary'}`} onClick={toggleAutoProcess}>
            {isProcessing ? 'Stop Autonomous Mode' : 'Start Autonomous Mode'}
          </button>
          <button className="btn" onClick={processBatch}>Process Batch (10)</button>
        </div>
      </header>

      {loadingStats ? (
        <p className="text-muted" style={{ textAlign: "center", marginTop: "1rem" }}>
          Loading recovery statistics …
        </p>
      ) : (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-title">At Risk Revenue (Queue + Processed)</div>
            <div className="stat-value">{formatCurrency(stats.total_potential_loss)}</div>
          </div>
          <div className="stat-card">
            <div className="stat-title">Successfully Recovered</div>
            <div className="stat-value highlight">{formatCurrency(stats.total_recovered_amount)}</div>
          </div>
          <div className="stat-card">
            <div className="stat-title">Recovery Rate</div>
            <div className="stat-value">{stats.recovery_rate_percent}%</div>
          </div>
          <div className="stat-card">
            <div className="stat-title">Events Analyzed</div>
            <div className="stat-value">{stats.processed_events} / {stats.total_events}</div>
          </div>
        </div>
      )}

      <div className="main-content">
        {/* Left Column: Live Intervention Feed */}
        <div className="panel">
          <div className="panel-header">
            <h2 className="panel-title">Live Intervention Feed</h2>
            <div className="flex items-center gap-2">
              <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: isProcessing ? '#10B981' : '#EF4444' }}></span>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                {isProcessing ? 'AI Agent Active' : 'System Idle'}
              </span>
            </div>
          </div>

          <div className="event-feed">
            {processedEvents.length === 0 ? (
              <div style={{ color: 'var(--text-secondary)', textAlign: 'center', padding: '2rem' }}>
                No events processed yet. Start the autonomous mode.
              </div>
            ) : (
              processedEvents.map((pe, idx) => (
                <div key={idx} className="event-item">
                  <div className="event-header">
                    <div className={`event-type ${pe.event.type}`}>
                      {formatType(pe.event.type)}
                    </div>
                    <div className="event-amount">{formatCurrency(pe.event.amount)}</div>
                  </div>

                  <div className="customer-info">
                    <span>👤 {pe.event.customer.name} (Risk: {pe.event.customer.risk_score})</span>
                    <span>🛑 Reason: {formatType(pe.event.raw_reason)}</span>
                    <span className={`status-badge ${pe.final_status}`}>
                      {pe.final_status.replace('_', ' ')}
                    </span>
                  </div>

                  {pe.decision && (
                    <div className="agent-box">
                      <div className="agent-header">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2z"></path><path d="M9 16v-2"></path><path d="M15 16v-2"></path></svg>
                        Aegis Master Agent &gt; {formatType(pe.decision.intervention)} ({(pe.decision.confidence * 100).toFixed(0)}% Match)
                      </div>
                      <div className="agent-reasoning">
                        {pe.decision.reasoning}
                      </div>
                      <div className="agent-action">
                        Action: {pe.decision.action_taken}
                      </div>
                      {extractAndRenderPayLink(pe.decision.action_taken)}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right Column: Merchant Copilot Interactive Panel */}
        <div className="panel copilot-panel">
          <div className="panel-header" style={{ marginBottom: '1rem' }}>
            <h2 className="panel-title">🤖 Aegis Copilot</h2>
            <span style={{ fontSize: '0.8rem', color: 'var(--accent-purple)', fontWeight: 600 }}>INTERACTIVE</span>
          </div>

          <div className="chat-history">
            {chatHistory.map((msg, idx) => (
              <div key={idx} className={`chat-message ${msg.role}`}>
                <div style={{ whiteSpace: 'pre-line' }}>
                  {msg.content}
                </div>
              </div>
            ))}
            {chatLoading && (
              <div className="chat-message assistant" style={{ fontStyle: 'italic', color: 'var(--text-secondary)' }}>
                Thinking...
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <div className="quick-actions" style={{ gridTemplateColumns: 'repeat(2, 1fr)' }}>
            <button className="quick-btn" onClick={() => triggerQuickAction("Show recovery stats")}>
              📊 Get Stats
            </button>
            <button className="quick-btn" onClick={() => triggerQuickAction("List recent failures")}>
              🔍 List Failures
            </button>
            <button className="quick-btn" onClick={() => triggerQuickAction("Explain why payments failed and suggest recoveries")}>
              💡 Recovery Playbook
            </button>
            <button className="quick-btn" onClick={() => triggerQuickAction("Can you apply a manual 10% discount for customer Aarav?")}>
              🎁 Offer Custom Discount
            </button>
            <button className="quick-btn" onClick={() => triggerQuickAction("Can we route failed transactions through Backup Gateway B?")}>
              ⚙️ Gateway Failover
            </button>
            <button className="quick-btn" onClick={() => triggerQuickAction("How do we offer split installments for high-value cart drops?")}>
              💳 Installment Plan
            </button>
          </div>

          <form className="chat-input-area" onSubmit={sendChatMessage}>
            <input
              type="text"
              className="chat-input"
              placeholder="Ask Copilot (e.g. 'Show stats' or 'Recover customer...')"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              disabled={chatLoading}
            />
            <button type="submit" className="btn primary" disabled={chatLoading} style={{ padding: '0 1.25rem' }}>
              Send
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default App;
