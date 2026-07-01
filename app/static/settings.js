/* Debt action buttons */
.debt-actions { white-space: nowrap; }
.btn-circle { width: 28px; height: 28px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: 14px; transition: all 0.2s; border: 1px solid #e5e7eb; background: white; cursor: pointer; gap: 4px; }
.btn-circle:hover { transform: scale(1.1); }
.btn-circle-success::after { content: '💰'; }
.btn-circle-danger::after { content: '🗑️'; }
.btn-circle-success:hover { background: #dcfce7; border-color: #22c55e; }
.btn-circle-danger:hover { background: #fee2e2; border-color: #ef4444; }