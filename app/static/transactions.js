// ─── Cashflow Web - Transactions Page ───

const API_BASE = '';

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
        credentials: 'include',
        ...options
    });
    if (res.status === 401) {
        window.location.href = '/login';
        throw new Error('Unauthorized');
    }
    return res.json();
}

// ─── State ───
let allTransactions = [];

// ─── Account & Category Dropdowns ───
async function updateAccountDropdowns() {
    try {
        const accounts = await api('/api/accounts');
        const txSelect = document.getElementById('tx-account');
        const toSelect = document.getElementById('tx-to-account');
        const options = accounts.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
        if (txSelect) txSelect.innerHTML = '<option value="">-- Pilih Akun --</option>' + options;
        if (toSelect) toSelect.innerHTML = '<option value="">-- Pilih Akun Tujuan --</option>' + options;
    } catch (e) {
        console.warn('Failed to load accounts', e);
    }
}

async function updateCategoryDropdown() {
    try {
        const categories = await api('/api/categories');
        const select = document.getElementById('tx-category');
        const currentType = document.getElementById('tx-type').value;
        let filtered = categories;
        if (currentType === 'income') filtered = categories.filter(c => c.type === 'income');
        else if (currentType === 'expense') filtered = categories.filter(c => c.type === 'expense');
        else if (currentType === 'transfer') filtered = categories.filter(c => c.type === 'transfer');
        select.innerHTML = '<option value="">-- Pilih Kategori --</option>' +
            filtered.map(c => `<option value="${c.name}">${c.name}</option>`).join('');
    } catch (e) {
        console.warn('Failed to load categories', e);
    }
}

// ─── Render Transactions ───
function renderTransactions(transactions) {
    const tbody = document.getElementById('transactions-body');
    if (transactions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="text-center py-5 text-gray-400">Belum ada transaksi</td></tr>';
        return;
    }
    tbody.innerHTML = transactions.map(tx => {
        const rekening = tx.type === 'transfer'
            ? `${tx.account_name || '?'} ↔ ${tx.to_account_name || '?'}`
            : (tx.account_name || '-');
        const incomeValue = tx.type === 'income' ? formatCurrency(tx.amount) : (tx.type === 'transfer' ? formatCurrency(tx.amount) : '-');
        const expenseValue = tx.type === 'expense' ? formatCurrency(tx.amount) : (tx.type === 'transfer' ? formatCurrency(tx.amount) : '-');
        const adminValue = tx.admin_fee && tx.admin_fee > 0 ? formatCurrency(tx.admin_fee) : '-';
        return `
            <tr>
                <td class="py-3 pr-3 text-sm text-gray-600">${formatDate(tx.date)}</td>
                <td class="py-3 pr-3 text-sm">${tx.category_name || '-'}</td>
                <td class="py-3 pr-3 text-sm">${rekening}</td>
                <td class="py-3 pr-3 text-sm text-right text-green-600">${incomeValue}</td>
                <td class="py-3 pr-3 text-sm text-right text-red-500">${expenseValue}</td>
                <td class="py-3 pr-3 text-sm text-right text-gray-400">${adminValue}</td>
                <td class="py-3 pr-3 text-sm text-gray-500">${tx.description || '—'}</td>
                <td class="py-3 text-sm">
                    <button onclick="deleteTransaction(${tx.id})" class="text-red-400 hover:text-red-600 text-xs font-medium">Hapus</button>
                </td>
            </tr>
        `;
    }).join('');
}

// ─── Load Transactions ───
async function loadTransactions() {
    try {
        allTransactions = await api('/api/transactions');
        renderTransactions(allTransactions);
    } catch (e) {
        console.warn('Failed to load transactions', e);
    }
}

async function deleteTransaction(id) {
    if (!confirm('Hapus transaksi ini?')) return;
    try {
        await api('/api/transactions/' + id, { method: 'DELETE' });
        await loadTransactions();
        // Also refresh dashboard summary if embedded
        if (typeof updateSummaryCards === 'function') updateSummaryCards();
    } catch (e) {
        alert('Gagal menghapus: ' + e.message);
    }
}

// ─── Filter ───
document.querySelectorAll('.btn-filter').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.btn-filter').forEach(b => {
            b.classList.remove('bg-warm-500', 'text-white');
            b.classList.add('bg-gray-100', 'text-gray-500');
        });
        btn.classList.remove('bg-gray-100', 'text-gray-500');
        btn.classList.add('bg-warm-500', 'text-white');
        const filter = btn.dataset.filter;
        if (filter === 'all') {
            renderTransactions(allTransactions);
        } else {
            renderTransactions(allTransactions.filter(t => t.type === filter));
        }
    });
});

// ─── Transaction Form Submit ───
document.getElementById('transaction-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
        type: document.getElementById('tx-type').value,
        date: document.getElementById('tx-date').value || todayISO(),
        category: document.getElementById('tx-category').value,
        account_id: parseInt(document.getElementById('tx-account').value),
        to_account_id: document.getElementById('tx-to-account').value ? parseInt(document.getElementById('tx-to-account').value) : null,
        amount: parseFloat(document.getElementById('tx-amount').value),
        admin_fee: parseFloat(document.getElementById('tx-admin').value) || 0,
        description: document.getElementById('tx-desc').value
    };

    try {
        await api('/api/transactions', { method: 'POST', body: JSON.stringify(payload) });
        e.target.reset();
        document.getElementById('tx-date').value = todayISO();
        await loadTransactions();
        await updateCategoryDropdown();
        await updateAccountDropdowns();
        if (typeof updateSummaryCards === 'function') updateSummaryCards();
    } catch (err) {
        alert('Gagal menyimpan: ' + err.message);
    }
});

// ─── Show/hide to-account ───
document.getElementById('tx-type').addEventListener('change', (e) => {
    const toGroup = document.getElementById('to-account-group');
    toGroup.style.display = e.target.value === 'transfer' ? 'block' : 'none';
    updateCategoryDropdown();
});

// ─── Init ───
document.addEventListener('DOMContentLoaded', async () => {
    await loadAccountsGrid();
    await updateAccountDropdowns();
    await updateCategoryDropdown();
    const txDate = document.getElementById('tx-date');
    if (txDate) txDate.value = todayISO();
    await loadTransactions();
});

// ─── Accounts Grid ───
async function loadAccountsGrid() {
    try {
        const accounts = await api('/api/accounts');
        const grid = document.getElementById('accounts-grid');
        if (!grid) return;
        if (accounts.length === 0) {
            grid.innerHTML = '<div class="bg-white rounded-xl p-4 border border-warm-100 col-span-full text-center text-sm text-gray-400">Belum ada rekening. Buka <strong>Pengaturan</strong> untuk menambah.</div>';
            return;
        }
        grid.innerHTML = accounts.map(a => `
            <div class="bg-white rounded-xl p-4 border border-warm-100">
                <p class="text-xs text-gray-400 font-medium truncate">${a.name}</p>
                <p class="text-sm font-bold text-gray-800 mt-1">${formatCurrency(a.balance || 0)}</p>
            </div>
        `).join('');
    } catch (e) {
        console.warn('Failed to load accounts grid', e);
    }
}
