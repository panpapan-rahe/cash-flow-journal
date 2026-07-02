// ─── Cashflow Web - Frontend ───

const API_BASE = '';

// ─── Helpers ───
function esc(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

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
        console.log('[DEBUG] Got 401, redirecting to login');
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
// ─── Transaction Form ───
const txForm = document.getElementById('transaction-form');
const txType = document.getElementById('tx-type');
const toAccountGroup = document.getElementById('to-account-group');



// ─── Category & Account Lists ───
async function updateAccountDropdowns() {
    try {
        const accounts = await api('/api/accounts');
        const txSelect = document.getElementById('tx-account');
        const toSelect = document.getElementById('tx-to-account');
        
        const options = accounts.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
        
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

async function updateDebtAccountDropdown() {
    try {
        const accounts = await api('/api/accounts');
        const select = document.getElementById('debt-account');
        if (!select) return;
        select.innerHTML = accounts.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
    } catch (e) {
        console.warn('Failed to load debt account dropdown', e);
    }
}

async function updatePayAccountDropdown() {
    try {
        const accounts = await api('/api/accounts');
        const select = document.getElementById('pay-account');
        if (!select) return;
        select.innerHTML = accounts.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
    } catch (e) {
        console.warn('Failed to load pay account dropdown', e);
    }
}

async function updateCategoryDropdown() {
    try {
        const categories = await api('/api/categories');
        const select = document.getElementById('tx-category');
        const typeEl = document.getElementById('tx-type');
        if (!select || !typeEl) return;
        const currentType = typeEl.value;

        let filtered = categories;
        if (currentType === 'income') filtered = categories.filter(c => c.type === 'income');
        else if (currentType === 'expense') filtered = categories.filter(c => c.type === 'expense');
        else if (currentType === 'transfer') filtered = categories.filter(c => c.type === 'transfer');

        select.innerHTML = '<option value="">-- Pilih Kategori --</option>' +
            filtered.map(c => `<option value="${c.name}">${c.name}</option>`).join('');
    } catch (e) {
        console.warn('Failed to load category dropdown', e);
    }
}

// ─── Transactions ───
let allTransactions = [];
let allDebts = [];

// ─── Forced Setup State ───
let forcedAccountSeq = 0;
let forcedAccounts = [];
let forcedCategories = [];
let forcedOpeningDebts = [];
let currentPayDebt = null;

async function loadTransactions() {
    try {
        allTransactions = await api('/api/transactions');
        renderTransactions(allTransactions.slice(0, 5));
        updateCategoryDropdown();
        updateAccountDropdowns();
    } catch (e) {
        console.warn('Failed to load transactions', e);
    }
}

function renderTransactions(transactions) {
    const tbody = document.getElementById('transactions-body');
    if (!tbody) return;

    if (transactions.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-state">Belum ada transaksi</td></tr>';
        return;
    }

    tbody.innerHTML = transactions.map(tx => {
        const rekening = tx.type === 'transfer'
            ? `${tx.account_name || '?'} <-> ${tx.to_account_name || '?'}`
            : (tx.account_name || '-');
        const incomeValue = tx.type === 'income' ? formatCurrency(tx.amount) : (tx.type === 'transfer' ? formatCurrency(tx.amount) : '-');
        const expenseValue = tx.type === 'expense' ? formatCurrency(tx.amount) : (tx.type === 'transfer' ? formatCurrency(tx.amount) : '-');
        const adminValue = tx.admin_fee && tx.admin_fee > 0 ? formatCurrency(tx.admin_fee) : '-';

        return `
            <tr>
                <td>${formatDate(tx.date)}</td>
                <td>${tx.category_name || '-'}</td>
                <td>${rekening}</td>
                <td class="amount-income">${incomeValue}</td>
                <td class="amount-expense">${expenseValue}</td>
                <td class="amount-admin">${adminValue}</td>
                <td>${tx.description || '-'}</td>
                <td>
                    <button class="btn-delete-circle" onclick="deleteTransaction(${tx.id})" aria-label="Hapus transaksi" title="Hapus transaksi"></button>
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
        await loadAccountsGrid();
        updateSummaryCards();
    } catch (e) {
        alert('Gagal menghapus: ' + e.message);
    }
}

// Filter removed — showing last 5 transactions only

// ─── Debts ───
async function loadDebts() {
    try {
        allDebts = await api('/api/debts');
        renderDebts(allDebts);
    } catch (e) {
        console.warn('Failed to load debts', e);
    }
}

function renderDebts(debts) {
    const tbody = document.getElementById('debts-body');
    
    if (debts.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">Belum ada hutang</td></tr>';
        return;
    }

    tbody.innerHTML = debts.map(d => {
        const remaining = d.amount_total - (d.total_paid || 0);
        const statusClass = d.status === 'paid' ? 'status-paid' : 'status-active';
        const statusText = d.status === 'paid' ? 'Lunas' : 'Aktif';
        const nameLabel = d.debt_kind === 'opening'
            ? `${d.person_name} <span title="Hutang Bawaan">📌</span>`
            : d.person_name;

        return `
            <tr>
                <td><strong>${nameLabel}</strong></td>
                <td>${d.account_name || '-'}</td>
                <td>${formatCurrency(d.amount_total)}</td>
                <td>${formatCurrency(d.total_paid || 0)}</td>
                <td>${formatCurrency(remaining)}</td>
                <td><span class="${statusClass}">${statusText}</span></td>
                <td class="debt-actions">
                    ${d.status !== 'paid' ? `<button class="btn-circle btn-circle-success" onclick="openPayModal(${d.id})" aria-label="Bayar hutang" title="Bayar hutang"></button>` : ''}
                    <button class="btn-circle btn-circle-danger" onclick="deleteDebt(${d.id})" aria-label="Hapus hutang" title="Hapus hutang"></button>
                </td>
            </tr>
        `;
    }).join('');
}

// Debt Modal
const debtModal = document.getElementById('debt-modal');
const debtForm = document.getElementById('debt-form');
const btnAddDebt = document.getElementById('btn-add-debt');

if (btnAddDebt && debtModal) {
    btnAddDebt.addEventListener('click', async () => {
        debtModal.style.display = 'flex';
        await updateDebtAccountDropdown();
    });
}

window.closeDebtModal = function() {
    debtModal.style.display = 'none';
    debtForm.reset();
    document.getElementById('pay-debt-id').value = '';
};

if (debtModal) {
    debtModal.addEventListener('click', (e) => {
        if (e.target === debtModal) closeDebtModal();
    });
}

if (debtForm) {
    debtForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            person_name: document.getElementById('debt-name').value,
            account_id: parseInt(document.getElementById('debt-account').value),
            amount_total: parseFloat(document.getElementById('debt-amount').value),
            admin_fee: parseFloat(document.getElementById('debt-admin').value) || 0,
            description: document.getElementById('debt-desc').value
        };
        try {
            await api('/api/debts', { method: 'POST', body: JSON.stringify(payload) });
            closeDebtModal();
            await loadDebts();
            await loadAccountsGrid();
            updateSummaryCards();
            await updateAccountDropdowns();
        } catch (e) {
            alert('Gagal: ' + e.message);
        }
    });
}

// Pay Modal
const payModal = document.getElementById('pay-modal');
const payForm = document.getElementById('pay-form');

window.openPayModal = async function(debtId) {
    currentPayDebt = allDebts.find(d => String(d.id) === String(debtId)) || null;
    document.getElementById('pay-debt-id').value = debtId;
    payModal.style.display = 'flex';
    await updatePayAccountDropdown();
    const payAccount = document.getElementById('pay-account');
    payAccount.disabled = false;
};

window.closePayModal = function() {
    payModal.style.display = 'none';
    payForm.reset();
    currentPayDebt = null;
    const payAccount = document.getElementById('pay-account');
    if (payAccount) payAccount.disabled = false;
};

if (payModal) payModal.addEventListener('click', (e) => {
    if (e.target === payModal) closePayModal();
});

if (payForm) payForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const debtId = document.getElementById('pay-debt-id').value;
    const payAccount = document.getElementById('pay-account');
    const payload = {
        payment_account_id: parseInt(payAccount.value),
        amount: parseFloat(document.getElementById('pay-amount').value),
        admin_fee: parseFloat(document.getElementById('pay-admin').value) || 0,
        note: document.getElementById('pay-note').value,
        date: todayISO()
    };
    try {
        await api('/api/debts/' + debtId + '/pay', { method: 'POST', body: JSON.stringify(payload) });
        closePayModal();
        await loadDebts();
        await loadAccountsGrid();
        updateSummaryCards();
        await updateAccountDropdowns();
    } catch (e) {
        alert('Gagal mencatat pembayaran: ' + e.message);
    }
});

async function deleteDebt(id) {
    if (!confirm('Hapus hutang ini? Riwayat pembayaran juga akan ikut terhapus.')) return;
    try {
        await api('/api/debts/' + id, { method: 'DELETE' });
        await loadDebts();
        updateSummaryCards();
    } catch (e) {
        alert('Gagal menghapus: ' + e.message);
    }
}

// ─── Settings (Accounts & Categories) ───
const settingsModal = document.getElementById('settings-modal');
const accountFormModal = document.getElementById('account-form-modal');
const categoryFormModal = document.getElementById('category-form-modal');
const forcedSetupModal = document.getElementById('forced-setup-modal');
const btnSettings = document.getElementById('btn-settings');
const btnAddAccount = document.getElementById('btn-add-account');

// Settings nav switching
document.querySelectorAll('.settings-tab').forEach(nav => {
    nav.addEventListener('click', () => {
        document.querySelectorAll('.settings-tab').forEach(n => n.classList.remove('bg-warm-100','text-warm-700'));
        document.querySelectorAll('.settings-tab').forEach(n => n.classList.add('text-gray-500','hover:bg-warm-50'));
        document.querySelectorAll('.settings-content').forEach(p => p.style.display = 'none');
        nav.classList.remove('text-gray-500','hover:bg-warm-50');
        nav.classList.add('bg-warm-100','text-warm-700');
        
        const panelId = 'content-' + nav.dataset.tab;
        const panel = document.getElementById(panelId);
        if (panel) panel.style.display = 'block';
        
        if (nav.dataset.tab === 'accounts') loadAccountsSettings();
        if (nav.dataset.tab === 'categories') loadCategoriesSettings();
    });
});

if (btnSettings) btnSettings.addEventListener('click', async () => {
    settingsModal.style.display = 'flex';
    await loadAccountsSettings();
});

const btnDeleteAccountExtra = document.getElementById('btn-delete-account-extra');
if (btnDeleteAccountExtra) btnDeleteAccountExtra.addEventListener('click', async () => {
    if (!confirm('Hapus akun ini? Semua data transaksi, hutang, dan rekening akan ikut terhapus.')) return;
    if (!confirm('Yakin? Tindakan ini tidak bisa dibatalkan.')) return;
    try {
        await api('/api/user', { method: 'DELETE' });
        window.location.href = '/login';
    } catch (e) {
        alert('Gagal menghapus akun: ' + e.message);
    }
});

if (btnAddAccount) btnAddAccount.addEventListener('click', () => {
    document.getElementById('account-form-title').textContent = 'Tambah Rekening';
    document.getElementById('account-id').value = '';
    document.getElementById('account-name').value = '';
    accountFormModal.style.display = 'flex';
});

const btnAddCategory = document.getElementById('btn-add-category');
if (btnAddCategory) btnAddCategory.addEventListener('click', () => {
    document.getElementById('category-id').value = '';
    document.getElementById('category-name').value = '';
    document.querySelector('input[name="category-type"][value="income"]').checked = true;
    categoryFormModal.style.display = 'flex';
});

window.closeSettingsModal = function() {
    settingsModal.style.display = 'none';
};

window.closeAccountFormModal = function() {
    accountFormModal.style.display = 'none';
    accountFormModal.classList.remove('forced');
};

window.closeCategoryFormModal = function() {
    categoryFormModal.style.display = 'none';
};

if (settingsModal) settingsModal.addEventListener('click', (e) => {
    if (e.target === settingsModal) closeSettingsModal();
});

if (accountFormModal) accountFormModal.addEventListener('click', (e) => {
    if (e.target === accountFormModal && !accountFormModal.classList.contains('forced')) closeAccountFormModal();
});

if (categoryFormModal) categoryFormModal.addEventListener('click', (e) => {
    if (e.target === categoryFormModal) closeCategoryFormModal();
});

if (forcedSetupModal) forcedSetupModal.addEventListener('click', (e) => {
    if (e.target === forcedSetupModal) {
        // Cannot close unless setup is complete
        alert('Anda harus menyelesaikan setup terlebih dahulu.');
    }
});

// Account form submit (create or update)
const accountForm = document.getElementById('account-form');
if (accountForm) accountForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('account-id').value;
    const name = document.getElementById('account-name').value.trim();
    const opening_balance = parseFloat(document.getElementById('account-opening-balance').value) || 0;
    const payload = { name, opening_balance };
    
    try {
        if (id) {
            await api('/api/accounts/' + id, { method: 'PUT', body: JSON.stringify(payload) });
        } else {
            await api('/api/accounts', { method: 'POST', body: JSON.stringify(payload) });
        }
        if (accountFormModal.classList.contains('forced')) {
            // Check if now has accounts
            const count = await api('/api/accounts/count');
            if (count.count >= 1) {
                accountFormModal.style.display = 'none';
                accountFormModal.classList.remove('forced');
                loadAccountsGrid();
                updateAccountDropdowns();
                // Show forced setup modal (sheet 1)
                showForcedSetupModal();
            }
        } else {
            closeAccountFormModal();
            await loadAccountsSettings();
            await loadAccountsGrid();
            updateSummaryCards();
            await updateAccountDropdowns();
        }
    } catch (e) {
        alert('Gagal menyimpan rekening: ' + e.message);
    }
});

// Category form submit
const categoryForm = document.getElementById('category-form');
if (categoryForm) categoryForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('category-name').value.trim();
    const type = document.querySelector('input[name="category-type"]:checked').value;
    const payload = { name, type };
    
    try {
        await api('/api/categories', { method: 'POST', body: JSON.stringify(payload) });
        closeCategoryFormModal();
        await loadCategoriesSettings();
        await updateCategoryDropdown();
    } catch (e) {
        alert('Gagal menambah kategori: ' + e.message);
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
            const opening = acc.opening_balance || 0;
            const balance = opening + income - expense - transferOut + transferIn;
            const balanceClass = balance < 0 ? 'amount-expense' : 'amount-income';

            return `
                <tr>
                    <td><strong>${acc.name}</strong></td>
                    <td class="amount-income">${formatCurrency(opening)}</td>
                    <td class="amount-income">+ ${formatCurrency(income)}</td>
                    <td class="amount-expense">- ${formatCurrency(expense)}</td>
                    <td class="amount-transfer">- ${formatCurrency(transferOut)}</td>
                    <td class="amount-transfer">+ ${formatCurrency(transferIn)}</td>
                    <td class="${balanceClass}"><strong>${formatCurrency(balance)}</strong></td>
                    <td>
                        <button class="btn btn-sm btn-secondary" onclick="editAccount(${acc.id}, '${acc.name}', ${opening})">Edit</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteAccount(${acc.id})">Hapus</button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        console.warn('Failed to load accounts settings', e);
    }
}

async function loadCategoriesSettings() {
    try {
        const categories = await api('/api/categories');
        const tbody = document.getElementById('categories-settings-body');
        
        if (categories.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="empty-state">Belum ada kategori</td></tr>';
            return;
        }

        tbody.innerHTML = categories.map(cat => {
            const typeLabel = cat.type === 'income' ? 'Pemasukan' : 'Pengeluaran';
            const typeBadge = cat.type === 'income' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700';
            return `
                <tr>
                    <td><strong>${cat.name}</strong></td>
                    <td><span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${typeBadge}">${typeLabel}</span></td>
                    <td>
                        <button class="btn btn-sm btn-danger" onclick="deleteCategory(${cat.id})">Hapus</button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        console.warn('Failed to load categories settings', e);
    }
}

window.editAccount = function(id, name, opening_balance) {
    document.getElementById('account-form-title').textContent = 'Edit Rekening';
    document.getElementById('account-id').value = id;
    document.getElementById('account-name').value = name;
    document.getElementById('account-opening-balance').value = opening_balance || 0;
    accountFormModal.style.display = 'flex';
};

window.deleteAccount = async function(id) {
    if (!confirm('Hapus rekening ini? Transaksi terkait tidak akan dihapus.')) return;
    try {
        await api('/api/accounts/' + id, { method: 'DELETE' });
        await loadAccountsSettings();
        await loadAccountsGrid();
        updateSummaryCards();
        await updateAccountDropdowns();
    } catch (e) {
        alert('Gagal menghapus: ' + e.message);
    }
};

window.deleteCategory = async function(id) {
    if (!confirm('Hapus kategori ini?')) return;
    try {
        await api('/api/categories/' + id, { method: 'DELETE' });
        await loadCategoriesSettings();
        await updateCategoryDropdown();
    } catch (e) {
        alert('Gagal menghapus: ' + e.message);
    }
};

// ─── Forced Setup Modal (First-time user) ───
function showForcedSetupModal() {
    forcedAccountSeq = 0;
    forcedAccounts = [];
    forcedCategories = [];
    forcedOpeningDebts = [];
    renderForcedAccounts();
    renderForcedCategories();
    renderForcedOpeningDebts();
    renderForcedOpeningDebtAccountOptions();
    document.getElementById('forced-sheet-1').style.display = 'block';
    document.getElementById('forced-sheet-2').style.display = 'none';
    document.getElementById('forced-sheet-3').style.display = 'none';
    forcedSetupModal.style.display = 'flex';
}

// Sheet 1: Accounts
const btnAddForcedAccount = document.getElementById('btn-add-forced-account');
if (btnAddForcedAccount) btnAddForcedAccount.addEventListener('click', () => {
    const name = document.getElementById('forced-account-name').value.trim() || 'Rekening';
    const opening = parseFloat(document.getElementById('forced-account-opening').value) || 0;
    if (name && name.trim()) {
        forcedAccountSeq += 1;
        forcedAccounts.push({ tempId: `fa-${forcedAccountSeq}`, name: name.trim(), opening_balance: opening });
        renderForcedAccounts();
        renderForcedOpeningDebtAccountOptions();
    }
});

function renderForcedAccounts() {
    const container = document.getElementById('forced-accounts-list');
    if (forcedAccounts.length === 0) {
        container.innerHTML = '<p class="empty-state">Belum ada rekening ditambahkan</p>';
    } else {
        container.innerHTML = forcedAccounts.map((acc, i) => `
            <div class="forced-item">
                <span>${acc.name} • ${formatCurrency(acc.opening_balance || 0)}</span>
                <div class="item-actions">
                    <button class="btn btn-sm btn-danger" onclick="removeForcedAccount(${i})">Hapus</button>
                </div>
            </div>
        `).join('');
    }
}

window.removeForcedAccount = function(index) {
    const removed = forcedAccounts[index];
    forcedAccounts.splice(index, 1);
    forcedOpeningDebts = forcedOpeningDebts.filter(d => d.account_temp_id !== removed.tempId);
    renderForcedAccounts();
    renderForcedOpeningDebtAccountOptions();
    renderForcedOpeningDebts();
};

const btnForcedNext = document.getElementById('btn-forced-next');
if (btnForcedNext) btnForcedNext.addEventListener('click', () => {
    if (forcedAccounts.length === 0) {
        alert('Minimal tambah 1 rekening terlebih dahulu.');
        return;
    }
    document.getElementById('forced-sheet-1').style.display = 'none';
    document.getElementById('forced-sheet-2').style.display = 'block';
});

// Sheet 2: Categories
const btnAddForcedCategory = document.getElementById('btn-add-forced-category');
if (btnAddForcedCategory) btnAddForcedCategory.addEventListener('click', () => {
    const name = document.getElementById('forced-category-name').value.trim();
    const type = document.querySelector('input[name="forced-cat-type"]:checked').value;
    if (!name) {
        alert('Nama kategori wajib diisi.');
        return;
    }
    forcedCategories.push({ name, type });
    document.getElementById('forced-category-name').value = '';
    renderForcedCategories();
});

function renderForcedCategories() {
    const container = document.getElementById('forced-categories-list');
    if (forcedCategories.length === 0) {
        container.innerHTML = '<p class="empty-state">Belum ada kategori ditambahkan</p>';
    } else {
        container.innerHTML = forcedCategories.map((cat, i) => {
            const typeLabel = cat.type === 'income' ? 'Pemasukan' : 'Pengeluaran';
            const typeBadge = cat.type === 'income' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700';
            return `
                <div class="forced-item">
                    <span>${cat.name} <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${typeBadge}">${typeLabel}</span></span>
                    <div class="item-actions">
                        <button class="btn btn-sm btn-danger" onclick="removeForcedCategory(${i})">Hapus</button>
                    </div>
                </div>
            `;
        }).join('');
    }
}

function renderForcedOpeningDebts() {
    const container = document.getElementById('forced-opening-debts-list');
    if (!container) return;
    if (forcedOpeningDebts.length === 0) {
        container.innerHTML = '<p class="empty-state">Belum ada hutang bawaan ditambahkan</p>';
        return;
    }
    container.innerHTML = forcedOpeningDebts.map((debt, i) => `
        <div class="forced-item">
            <span>${debt.name} • ${debt.account_name} • ${formatCurrency(debt.amount)}</span>
            <div class="item-actions">
                <button class="btn btn-sm btn-danger" onclick="removeForcedOpeningDebt(${i})">Hapus</button>
            </div>
        </div>
    `).join('');
}

function refreshOpeningDebtAccountSelect() {
    const select = document.getElementById('forced-opening-debt-account');
    if (!select) return;
    if (forcedAccounts.length === 0) {
        select.innerHTML = '<option value="">-- Tambah rekening dulu --</option>';
        select.disabled = true;
        return;
    }
    select.disabled = false;
    select.innerHTML = '<option value="">-- Pilih Rekening --</option>' + forcedAccounts.map(acc => `<option value="${acc.tempId}">${acc.name}</option>`).join('');
}

const btnForcedNextDebt = document.getElementById('btn-forced-next-debt');
if (btnForcedNextDebt) btnForcedNextDebt.addEventListener('click', () => {
    if (forcedCategories.length === 0) {
        alert('Minimal tambah 1 kategori terlebih dahulu.');
        return;
    }
    document.getElementById('forced-sheet-2').style.display = 'none';
    document.getElementById('forced-sheet-3').style.display = 'block';
    refreshOpeningDebtAccountSelect();
    renderForcedOpeningDebts();
});

const btnAddForcedOpeningDebt = document.getElementById('btn-add-forced-opening-debt');
if (btnAddForcedOpeningDebt) btnAddForcedOpeningDebt.addEventListener('click', () => {
    const name = document.getElementById('forced-opening-debt-name').value.trim() || 'Hutang Bawaan';
    const accountTempId = document.getElementById('forced-opening-debt-account').value;
    const account = forcedAccounts.find(a => a.tempId === accountTempId);
    const amount = parseFloat(document.getElementById('forced-opening-debt-amount').value);
    const desc = document.getElementById('forced-opening-debt-desc').value.trim();
    if (!accountTempId || !account) {
        alert('Pilih rekening terkait untuk hutang bawaan.');
        return;
    }
    if (!amount || amount <= 0) {
        alert('Jumlah hutang harus diisi.');
        return;
    }
    forcedOpeningDebts.push({
        name,
        account_temp_id: accountTempId,
        account_name: account.name,
        amount,
        description: desc,
    });
    document.getElementById('forced-opening-debt-name').value = 'Hutang Bawaan';
    document.getElementById('forced-opening-debt-amount').value = '';
    document.getElementById('forced-opening-debt-desc').value = '';
    renderForcedOpeningDebts();
});

window.removeForcedOpeningDebt = function(index) {
    forcedOpeningDebts.splice(index, 1);
    renderForcedOpeningDebts();
};

window.removeForcedCategory = function(index) {
    forcedCategories.splice(index, 1);
    renderForcedCategories();
};

const btnForcedBack = document.getElementById('btn-forced-back');
if (btnForcedBack) btnForcedBack.addEventListener('click', () => {
    document.getElementById('forced-sheet-2').style.display = 'none';
    document.getElementById('forced-sheet-1').style.display = 'block';
});

const btnForcedBackDebt = document.getElementById('btn-forced-back-debt');
if (btnForcedBackDebt) btnForcedBackDebt.addEventListener('click', () => {
    document.getElementById('forced-sheet-3').style.display = 'none';
    document.getElementById('forced-sheet-2').style.display = 'block';
});

const btnForcedSelesai = document.getElementById('btn-forced-selesai');
if (btnForcedSelesai) btnForcedSelesai.addEventListener('click', async () => {
    if (forcedCategories.length === 0) {
        alert('Minimal tambah 1 kategori terlebih dahulu.');
        return;
    }
    
    try {
        const accountIdMap = new Map();
        // Save all accounts and map temp IDs to DB IDs
        for (const acc of forcedAccounts) {
            const res = await api('/api/accounts', { method: 'POST', body: JSON.stringify({ name: acc.name, opening_balance: acc.opening_balance || 0 }) });
            if (res && res.id) accountIdMap.set(acc.tempId, res.id);
        }
        // Save all categories
        for (const cat of forcedCategories) {
            await api('/api/categories', { method: 'POST', body: JSON.stringify(cat) });
        }
        // Save opening debts (optional)
        for (const debt of forcedOpeningDebts) {
            const realAccountId = accountIdMap.get(debt.account_temp_id);
            if (!realAccountId) continue;
            await api('/api/debts', {
                method: 'POST',
                body: JSON.stringify({
                    person_name: debt.name,
                    account_id: realAccountId,
                    amount_total: debt.amount,
                    description: debt.description || 'Hutang Bawaan',
                    debt_kind: 'opening'
                })
            });
        }
        
        forcedSetupModal.style.display = 'none';
        forcedAccounts = [];
        forcedCategories = [];
        forcedOpeningDebts = [];
        forcedAccountSeq = 0;
        await renderAll();
        await updateAccountDropdowns();
        await updateCategoryDropdown();
    } catch (e) {
        alert('Gagal menyimpan setup: ' + e.message);
    }
});

// ─── Accounts Grid (Dashboard) ───
async function loadAccountsGrid() {
    try {
        const accounts = await api('/api/accounts');
        const grid = document.getElementById('accounts-grid');
        
        if (accounts.length === 0) {
            grid.innerHTML = '<div class="empty-state">Belum ada rekening. Buka Pengaturan untuk menambah.</div>';
            // Show forced setup modal
            showForcedSetupModal();
            updateAccountDropdowns();
            return;
        }

        grid.innerHTML = accounts.map(acc => {
            const income = acc.income || 0;
            const expense = acc.expense || 0;
            const transferOut = acc.transfer_out || 0;
            const transferIn = acc.transfer_in || 0;
            const opening = acc.opening_balance || 0;
            const balance = acc.balance ?? (opening + income - expense - transferOut + transferIn);
            const balanceClass = balance < 0 ? 'negative' : '';

            return `
                <div class="bg-white rounded-xl p-5 border border-warm-100 relative hover:border-warm-300 transition-colors shadow-sm hover:shadow">
                    <button class="absolute top-3 right-3 text-[11px] text-warm-500 hover:text-warm-700 font-medium" onclick="openAccountDetail(${acc.id}, '${acc.name}')">Detail</button>
                    <div class="text-sm font-bold text-gray-700 mb-1 truncate pr-12">${acc.name}</div>
                    <div class="text-base font-bold ${balanceClass === 'negative' ? 'text-red-500' : 'text-warm-700'} mt-1">${formatCurrency(balance)}</div>
                    <div class="flex gap-3 mt-3 pt-3 border-t border-gray-100 text-xs text-gray-500">
                        <span title="Pemasukan" class="text-green-600">+${formatCurrency(income)}</span>
                        <span title="Pengeluaran" class="text-red-400">-${formatCurrency(expense)}</span>
                    </div>
                </div>
            `;
        }).join('');

        // Add empty dummy cards to fill the last row
        const remainder = accounts.length % 4;
        if (remainder > 0 && accounts.length > 0) {
            const dummyCount = 4 - remainder;
            for (let i = 0; i < dummyCount; i++) {
                grid.innerHTML += `<div class="bg-transparent rounded-xl border border-dashed border-warm-200"></div>`;
            }
        }

        // Update transaction form dropdowns
        updateAccountDropdowns();
    } catch (e) {
        console.warn('Failed to load accounts grid', e);
    }
}

// ─── Render All ───
async function renderAll() {
    try {
        await Promise.all([loadTransactions(), loadDebts(), loadAccountsGrid()]);
        await updateCategoryDropdown();
        await updateAccountDropdowns();
        updateSummaryCards();
    } catch (e) {
        console.error('[renderAll] Error:', e);
    }
}

// ─── Summary Cards ───
function updateSummaryCards() {
    console.log('[DEBUG] Updating summary cards...');
    
    // Sum balance from all accounts
    fetch('/api/accounts', { credentials: 'include' })
        .then(r => r.json())
        .then(accounts => {
            const total = accounts.reduce((sum, a) => sum + (parseFloat(a.balance) || 0), 0);
            const el = document.getElementById('sum-balance');
            if (el) el.textContent = formatCurrency(total);
            console.log('[DEBUG] Balance updated:', total);
        })
        .catch(err => console.error('[DEBUG] Failed update balance:', err));

    // Sum active debt
    const debtEl = document.getElementById('sum-debt');
    if (debtEl && typeof allDebts !== 'undefined' && Array.isArray(allDebts)) {
        const totalDebt = allDebts.reduce((sum, d) => {
            const paid = parseFloat(d.total_paid) || 0;
            const total = parseFloat(d.amount_total) || 0;
            return sum + (total - paid);
        }, 0);
        debtEl.textContent = formatCurrency(totalDebt);
        console.log('[DEBUG] Debt updated:', totalDebt);
    } else {
        console.warn('[DEBUG] allDebts not ready or debtEl missing');
    }
}

// ─── Init ───
document.addEventListener('DOMContentLoaded', () => {
    console.log('[DEBUG] DOMContentLoaded fired');
    const loginPage = document.querySelector('.login-page');
    if (loginPage) return; // on login page
    
    const txDateEl = document.getElementById('tx-date');
    if (txDateEl) txDateEl.value = todayISO();
    
    // Attach event listeners immediately (don't wait for checkAuth)
    attachTransactionFormListener();
    attachTypeChangeListener();
    
    // Load data
    checkAuth();
});

function attachTransactionFormListener() {
    const txForm = document.getElementById('transaction-form');
    console.log('[DEBUG] attachTransactionFormListener called, txForm:', txForm);
    if (!txForm) return;
    
    txForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        console.log('[DEBUG] Form submitted!');
        
        const payload = {
            type: txType.value,
            amount: parseFloat(document.getElementById('tx-amount').value),
            admin_fee: parseFloat(document.getElementById('tx-admin').value) || 0,
            category: txType.value === 'transfer' ? 'Mutasi' : document.getElementById('tx-category').value,
            account_id: parseInt(document.getElementById('tx-account').value),
            description: document.getElementById('tx-desc').value,
            date: document.getElementById('tx-date').value
        };

        if (txType.value === 'transfer') {
            const toAccountId = parseInt(document.getElementById('tx-to-account').value);
            if (!toAccountId || toAccountId === payload.account_id) {
                alert('Pilih akun tujuan yang berbeda dari akun asal.');
                return;
            }
            payload.to_account_id = toAccountId;
        }

        console.log('[DEBUG] Sending payload:', JSON.stringify(payload));

        try {
            const result = await fetch('/api/transactions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify(payload)
            });
            console.log('[DEBUG] Response status:', result.status, 'ok:', result.ok);
            const text = await result.text();
            console.log('[DEBUG] Response text:', text.substring(0, 300));
            let data;
            try { data = JSON.parse(text); } catch(e) { console.log('[DEBUG] Not JSON!'); throw new Error('Server returned HTML, not JSON'); }
            console.log('[DEBUG] Response data:', JSON.stringify(data));
            if (result.ok) {
                txForm.reset();
                document.getElementById('tx-date').value = todayISO();
                await loadTransactions();
                await loadAccountsGrid();
                updateSummaryCards();
                await updateAccountDropdowns();
                await updateCategoryDropdown();
            }
        } catch (e) {
            alert('Gagal menyimpan transaksi: ' + e.message);
        }
    });
}

function attachTypeChangeListener() {
    const txCategory = document.getElementById('tx-category');
    if (!txCategory) return;
    const categoryGroup = txCategory.closest('.form-group');
    const txForm = document.getElementById('transaction-form');
    const txType = document.getElementById('tx-type');
    const toAccountGroup = document.getElementById('to-account-group');
    const txAccountLabel = document.getElementById('tx-account-label');
    const txToAccountLabel = document.getElementById('tx-to-account-label');

    if (!txType) return;
    txType.addEventListener('change', () => {
        const isTransfer = txType.value === 'transfer';
        if (txForm) {
            txForm.classList.toggle('mode-transfer', isTransfer);
            txForm.classList.toggle('mode-standard', !isTransfer);
        }
        if (toAccountGroup) toAccountGroup.style.display = isTransfer ? 'flex' : 'none';

        if (isTransfer) {
            if (txAccountLabel) txAccountLabel.textContent = 'Bank Asal';
            if (txToAccountLabel) txToAccountLabel.textContent = 'Bank Tujuan';
            txCategory.value = 'Mutasi';
            txCategory.disabled = true;
            if (categoryGroup) categoryGroup.style.display = 'none';
        } else {
            if (txAccountLabel) txAccountLabel.textContent = 'Akun';
            if (txToAccountLabel) txToAccountLabel.textContent = 'Ke Akun';
            txCategory.disabled = false;
            txCategory.value = '';
            if (categoryGroup) categoryGroup.style.display = '';
            updateCategoryDropdown();
        }
    });
}

// ─── Account Detail Modal ───
window.openAccountDetail = async function(accountId, accountName) {
    const modal = document.getElementById('account-detail-modal');
    const title = document.getElementById('account-detail-title');
    const body = document.getElementById('account-detail-body');
    if (!modal || !title || !body) return;

    title.textContent = `Detail — ${accountName}`;
    body.innerHTML = '<div class="text-sm text-gray-400 py-6 text-center">Memuat...</div>';
    modal.style.display = 'flex';

    try {
        const accounts = await api('/api/accounts');
        const acc = accounts.find(a => String(a.id) === String(accountId));
        if (!acc) {
            body.innerHTML = '<div class="text-sm text-gray-400 py-6 text-center">Data akun tidak ditemukan.</div>';
            return;
        }
        const opening = acc.opening_balance || 0;
        const income = acc.income || 0;
        const expense = acc.expense || 0;
        const transferOut = acc.transfer_out || 0;
        const transferIn = acc.transfer_in || 0;
        const balance = acc.balance ?? (opening + income - expense - transferOut + transferIn);
        const balanceClass = balance < 0 ? 'text-red-500' : 'text-warm-700';

        body.innerHTML = `
            <div class="text-center mb-5">
                <p class="text-xs text-gray-400 uppercase tracking-wide">Saldo Saat Ini</p>
                <p class="text-2xl font-bold ${balanceClass} mt-1">${formatCurrency(balance)}</p>
            </div>

            <div class="relative grid grid-cols-2 gap-3 mb-2">
                <div class="bg-green-50 rounded-lg p-4 text-center">
                    <p class="text-[11px] text-gray-400 uppercase tracking-wide">Pemasukan</p>
                    <p class="text-base font-bold text-green-600 mt-1">+ ${formatCurrency(income)}</p>
                </div>
                <div class="bg-red-50 rounded-lg p-4 text-center">
                    <p class="text-[11px] text-gray-400 uppercase tracking-wide">Pengeluaran</p>
                    <p class="text-base font-bold text-red-500 mt-1">− ${formatCurrency(expense)}</p>
                </div>
                <div class="bg-blue-50 rounded-lg p-4 text-center">
                    <p class="text-[11px] text-gray-400 uppercase tracking-wide">Mutasi Masuk</p>
                    <p class="text-base font-bold text-blue-600 mt-1">+ ${formatCurrency(transferIn)}</p>
                </div>
                <div class="bg-amber-50 rounded-lg p-4 text-center">
                    <p class="text-[11px] text-gray-400 uppercase tracking-wide">Mutasi Keluar</p>
                    <p class="text-base font-bold text-amber-600 mt-1">− ${formatCurrency(transferOut)}</p>
                </div>

                <div class="col-span-2 flex justify-end pt-1">
                    <span class="text-[11px] text-gray-400 italic">Saldo awal: ${formatCurrency(opening)}</span>
                </div>
            </div>
        `;
    } catch (e) {
        body.innerHTML = '<div class="text-sm text-gray-400 py-6 text-center">Gagal memuat data akun.</div>';
        console.warn('Failed to load account detail', e);
    }
};

window.closeAccountDetailModal = function() {
    const modal = document.getElementById('account-detail-modal');
    if (modal) modal.style.display = 'none';
};
