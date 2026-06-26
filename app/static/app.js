// ─── Cashflow Web - Frontend ───

const API_BASE = '';

// ─── Helpers ───
function formatCurrency(num) {
    return 'Rp ' + Number(num).toLocaleString('id-ID');
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    const d = new Date(dateStr);
    return d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' });
}

function todayISO() {
    return new Date().toISOString().split('T')[0];
}

async function api(path, options = {}) {
    const res = await fetch(API_BASE + path, {
        headers: { 'Content-Type': 'application/json' },
        ...options
    });
    if (res.status === 401) {
        window.location.href = '/login';
        throw new Error('Unauthorized');
    }
    return res.json();
}

// ─── Auth ───
let currentUser = null;

async function checkAuth() {
    try {
        const data = await api('/api/summary');
        currentUser = data;
        renderAll();
    } catch {
        // not logged in, stay on login page
    }
}

// ─── Summary ───
async function loadSummary() {
    try {
        const data = await api('/api/summary');
        document.getElementById('summary-income').textContent = formatCurrency(data.income);
        document.getElementById('summary-expense').textContent = formatCurrency(data.expense);
        document.getElementById('summary-balance').textContent = formatCurrency(data.balance);
        document.getElementById('summary-debt').textContent = formatCurrency(data.pending_debt);
    } catch (e) {
        console.warn('Failed to load summary', e);
    }
}

// ─── Transaction Form ───
const txForm = document.getElementById('transaction-form');
const txType = document.getElementById('tx-type');
const toAccountGroup = document.getElementById('to-account-group');

txType.addEventListener('change', () => {
    toAccountGroup.style.display = txType.value === 'transfer' ? 'flex' : 'none';
    // Update category datalist based on type
    updateCategoryDatalist();
});

txForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const payload = {
        type: txType.value,
        amount: parseFloat(document.getElementById('tx-amount').value),
        category: document.getElementById('tx-category').value,
        account: document.getElementById('tx-account').value || 'Utama',
        description: document.getElementById('tx-desc').value,
        date: document.getElementById('tx-date').value
    };

    if (txType.value === 'transfer') {
        payload.to_account = document.getElementById('tx-to-account').value || 'Lainnya';
    }

    try {
        const result = await api('/api/transactions', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
        if (result.ok) {
            txForm.reset();
            document.getElementById('tx-date').value = todayISO();
            await loadTransactions();
            await loadSummary();
        }
    } catch (e) {
        alert('Gagal menyimpan transaksi: ' + e.message);
    }
});

// ─── Category & Account Lists ───
async function updateCategoryDatalist() {
    try {
        const categories = await api('/api/categories');
        const datalist = document.getElementById('category-list');
        const currentType = txType.value; // income atau expense
        datalist.innerHTML = categories
            .filter(c => (currentType === 'transfer' || c.type === (currentType === 'income' ? 'income' : 'expense')))
            .map(c => `<option value="${c.name}">`)
            .join('');
    } catch (e) {
        console.warn('Failed to load categories', e);
    }
}

async function updateAccountDropdowns() {
    try {
        const accounts = await api('/api/accounts');
        const txSelect = document.getElementById('tx-account');
        const toSelect = document.getElementById('tx-to-account');
        
        const options = accounts.map(a => `<option value="${a.name}">${a.name}</option>`).join('');
        
        if (txSelect) {
            txSelect.innerHTML = '<option value="">-- Pilih Akun --</option>' + options;
        }
        if (toSelect) {
            toSelect.innerHTML = '<option value="">-- Pilih Akun Tujuan --</option>' + options;
        }
    } catch (e) {
        console.warn('Failed to load account dropdowns', e);
    }
}

// ─── Transactions ───
let allTransactions = [];

async function loadTransactions() {
    try {
        allTransactions = await api('/api/transactions');
        renderTransactions(allTransactions);
        updateCategoryDatalist();
        updateAccountDropdowns();
    } catch (e) {
        console.warn('Failed to load transactions', e);
    }
}

function renderTransactions(transactions) {
    const tbody = document.getElementById('transactions-body');
    
    if (transactions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">Belum ada transaksi</td></tr>';
        return;
    }

    const typeLabels = { income: 'Masuk', expense: 'Keluar', transfer: 'Mutasi' };

    tbody.innerHTML = transactions.map(tx => {
        const typeClass = 'badge-' + tx.type;
        const amountClass = 'amount-' + tx.type;
        const amountPrefix = tx.type === 'income' ? '+' : tx.type === 'expense' ? '-' : '⟷';
        const txAccount = tx.type === 'transfer' ? 
            `${tx.account_name || '?'} → ${tx.to_account_name || '?'}` : 
            (tx.account_name || '-');

        return `
            <tr>
                <td>${formatDate(tx.date)}</td>
                <td><span class="badge ${typeClass}">${typeLabels[tx.type] || tx.type}</span></td>
                <td>${tx.category_name || '-'}</td>
                <td>${txAccount}</td>
                <td class="${amountClass}">${amountPrefix} ${formatCurrency(tx.amount)}</td>
                <td>${tx.description || '-'}</td>
                <td>
                    <button class="btn btn-sm btn-danger" onclick="deleteTransaction(${tx.id})">Hapus</button>
                </td>
            </tr>
        `;
    }).join('');
}

async function deleteTransaction(id) {
    if (!confirm('Hapus transaksi ini?')) return;
    try {
        await api('/api/transactions/' + id, { method: 'DELETE' });
        await loadTransactions();
        await loadSummary();
    } catch (e) {
        alert('Gagal menghapus: ' + e.message);
    }
}

// Filter transactions
document.querySelectorAll('.btn-filter').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const filter = btn.dataset.filter;
        if (filter === 'all') {
            renderTransactions(allTransactions);
        } else {
            renderTransactions(allTransactions.filter(t => t.type === filter));
        }
    });
});

// ─── Debts ───
async function loadDebts() {
    try {
        const debts = await api('/api/debts');
        renderDebts(debts);
    } catch (e) {
        console.warn('Failed to load debts', e);
    }
}

function renderDebts(debts) {
    const tbody = document.getElementById('debts-body');
    
    if (debts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="empty-state">Belum ada hutang</td></tr>';
        return;
    }

    tbody.innerHTML = debts.map(d => {
        const remaining = d.amount_total - (d.total_paid || 0);
        const statusClass = d.status === 'paid' ? 'status-paid' : 'status-active';
        const statusText = d.status === 'paid' ? 'Lunas' : 'Aktif';

        return `
            <tr>
                <td><strong>${d.person_name}</strong></td>
                <td>${formatCurrency(d.amount_total)}</td>
                <td>${formatCurrency(d.total_paid || 0)}</td>
                <td>${formatCurrency(remaining)}</td>
                <td><span class="${statusClass}">${statusText}</span></td>
                <td class="debt-actions">
                    ${d.status !== 'paid' ? `<button class="btn btn-sm btn-success" onclick="openPayModal(${d.id})">Bayar</button>` : ''}
                    <button class="btn btn-sm btn-danger" onclick="deleteDebt(${d.id})">Hapus</button>
                </td>
            </tr>
        `;
    }).join('');
}

// Debt Modal
const debtModal = document.getElementById('debt-modal');
const debtForm = document.getElementById('debt-form');
const btnAddDebt = document.getElementById('btn-add-debt');

btnAddDebt.addEventListener('click', () => {
    debtModal.style.display = 'flex';
});

window.closeDebtModal = function() {
    debtModal.style.display = 'none';
    debtForm.reset();
    document.getElementById('pay-debt-id').value = '';
};

debtModal.addEventListener('click', (e) => {
    if (e.target === debtModal) closeDebtModal();
});

debtForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
        person_name: document.getElementById('debt-name').value,
        amount_total: parseFloat(document.getElementById('debt-amount').value),
        description: document.getElementById('debt-desc').value
    };
    try {
        await api('/api/debts', { method: 'POST', body: JSON.stringify(payload) });
        closeDebtModal();
        await loadDebts();
        await loadSummary();
    } catch (e) {
        alert('Gagal menambah hutang: ' + e.message);
    }
});

// Pay Modal
const payModal = document.getElementById('pay-modal');
const payForm = document.getElementById('pay-form');

window.openPayModal = function(debtId) {
    document.getElementById('pay-debt-id').value = debtId;
    payModal.style.display = 'flex';
};

window.closePayModal = function() {
    payModal.style.display = 'none';
    payForm.reset();
};

payModal.addEventListener('click', (e) => {
    if (e.target === payModal) closePayModal();
});

payForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const debtId = document.getElementById('pay-debt-id').value;
    const payload = {
        amount: parseFloat(document.getElementById('pay-amount').value),
        note: document.getElementById('pay-note').value,
        date: todayISO()
    };
    try {
        await api('/api/debts/' + debtId + '/pay', { method: 'POST', body: JSON.stringify(payload) });
        closePayModal();
        await loadDebts();
        await loadSummary();
    } catch (e) {
        alert('Gagal mencatat pembayaran: ' + e.message);
    }
});

async function deleteDebt(id) {
    if (!confirm('Hapus hutang ini? Riwayat pembayaran juga akan ikut terhapus.')) return;
    try {
        await api('/api/debts/' + id, { method: 'DELETE' });
        await loadDebts();
        await loadSummary();
    } catch (e) {
        alert('Gagal menghapus: ' + e.message);
    }
}

// ─── Settings (Accounts) ───
const settingsModal = document.getElementById('settings-modal');
const accountFormModal = document.getElementById('account-form-modal');
const btnSettings = document.getElementById('btn-settings');
const btnAddAccount = document.getElementById('btn-add-account');

btnSettings.addEventListener('click', async () => {
    settingsModal.style.display = 'flex';
    await loadAccountsSettings();
});

btnAddAccount.addEventListener('click', () => {
    document.getElementById('account-form-title').textContent = 'Tambah Rekening';
    document.getElementById('account-id').value = '';
    document.getElementById('account-name').value = '';
    accountFormModal.style.display = 'flex';
});

window.closeSettingsModal = function() {
    settingsModal.style.display = 'none';
};

window.closeAccountFormModal = function() {
    accountFormModal.style.display = 'none';
};

settingsModal.addEventListener('click', (e) => {
    if (e.target === settingsModal) closeSettingsModal();
});

accountFormModal.addEventListener('click', (e) => {
    if (e.target === accountFormModal) closeAccountFormModal();
});

// ─── Forced Account Modal (first-time user) ───
const forcedAccountModal = document.getElementById('account-form-modal');

// Override forced modal behavior
function showForcedAccountModal() {
    document.getElementById('account-form-title').textContent = 'Tambah Rekening Pertama';
    document.getElementById('account-id').value = '';
    document.getElementById('account-name').value = '';
    forcedAccountModal.style.display = 'flex';
    forcedAccountModal.classList.add('forced');
}

function closeForcedAccountModal() {
    // Only allow close if user has at least 1 account
    api('/api/accounts/count').then(data => {
        if (data.count >= 1) {
            forcedAccountModal.style.display = 'none';
            forcedAccountModal.classList.remove('forced');
            loadAccountsGrid();
            updateAccountDropdowns();
        } else {
            alert('Minimal 1 rekening harus dibuat terlebih dahulu.');
        }
    });
}

forcedAccountModal.addEventListener('click', (e) => {
    if (e.target === forcedAccountModal) {
        closeForcedAccountModal();
    }
});

// Account form submit (create or update)
document.getElementById('account-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('account-id').value;
    const name = document.getElementById('account-name').value.trim();
    const payload = { name };
    
    try {
        if (id) {
            await api('/api/accounts/' + id, { method: 'PUT', body: JSON.stringify(payload) });
        } else {
            await api('/api/accounts', { method: 'POST', body: JSON.stringify(payload) });
        }
        if (forcedAccountModal.classList.contains('forced')) {
            closeForcedAccountModal();
        } else {
            closeAccountFormModal();
            await loadAccountsSettings();
            await updateAccountDropdowns();
        }
        await loadAccountsGrid();
        await updateAccountDropdowns();
    } catch (e) {
        alert('Gagal menyimpan rekening: ' + e.message);
    }
});

async function loadAccountsSettings() {
    try {
        const accounts = await api('/api/accounts');
        const tbody = document.getElementById('accounts-settings-body');
        
        if (accounts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-state">Belum ada rekening</td></tr>';
            return;
        }

        tbody.innerHTML = accounts.map(acc => {
            const income = acc.income || 0;
            const expense = acc.expense || 0;
            const transferOut = acc.transfer_out || 0;
            const transferIn = acc.transfer_in || 0;
            const balance = income - expense - transferOut + transferIn;
            const balanceClass = balance < 0 ? 'amount-expense' : 'amount-income';

            return `
                <tr>
                    <td><strong>${acc.name}</strong></td>
                    <td class="amount-income">+ ${formatCurrency(income)}</td>
                    <td class="amount-expense">- ${formatCurrency(expense)}</td>
                    <td class="amount-transfer">- ${formatCurrency(transferOut)}</td>
                    <td class="amount-transfer">+ ${formatCurrency(transferIn)}</td>
                    <td class="${balanceClass}"><strong>${formatCurrency(balance)}</strong></td>
                    <td>
                        <button class="btn btn-sm btn-secondary" onclick="editAccount(${acc.id}, '${acc.name}')">Edit</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteAccount(${acc.id})">Hapus</button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        console.warn('Failed to load accounts settings', e);
    }
}

window.editAccount = function(id, name) {
    document.getElementById('account-form-title').textContent = 'Edit Rekening';
    document.getElementById('account-id').value = id;
    document.getElementById('account-name').value = name;
    accountFormModal.style.display = 'flex';
};

window.deleteAccount = async function(id) {
    if (!confirm('Hapus rekening ini? Transaksi terkait tidak akan dihapus.')) return;
    try {
        await api('/api/accounts/' + id, { method: 'DELETE' });
        await loadAccountsSettings();
        await updateAccountDropdowns();
    } catch (e) {
        alert('Gagal menghapus: ' + e.message);
    }
};

// ─── Accounts Grid (Dashboard) ───
async function loadAccountsGrid() {
    try {
        const accounts = await api('/api/accounts');
        const grid = document.getElementById('accounts-grid');
        
        if (accounts.length === 0) {
            grid.innerHTML = '<div class="empty-state">Belum ada rekening. Buka Pengaturan untuk menambah.</div>';
            // Show forced modal (cannot close without creating at least 1 account)
            showForcedAccountModal();
            updateAccountDropdowns();
            return;
        }

        grid.innerHTML = accounts.map(acc => {
            const income = acc.income || 0;
            const expense = acc.expense || 0;
            const transferOut = acc.transfer_out || 0;
            const transferIn = acc.transfer_in || 0;
            const balance = income - expense - transferOut + transferIn;
            const balanceClass = balance < 0 ? 'negative' : '';

            return `
                <div class="account-card">
                    <div class="account-name">${acc.name}</div>
                    <div class="account-balance ${balanceClass}">${formatCurrency(balance)}</div>
                    <div class="account-stats">
                        <span>↑ ${formatCurrency(income)}</span>
                        <span>↓ ${formatCurrency(expense)}</span>
                    </div>
                </div>
            `;
        }).join('');
    } catch (e) {
        console.warn('Failed to load accounts grid', e);
    }
}

// ─── Render All ───
async function renderAll() {
    await Promise.all([loadSummary(), loadTransactions(), loadDebts(), loadAccountsGrid()]);
}

// ─── Init ───
document.addEventListener('DOMContentLoaded', () => {
    const loginPage = document.querySelector('.login-page');
    if (loginPage) return; // on login page
    
    document.getElementById('tx-date').value = todayISO();
    checkAuth();
});
