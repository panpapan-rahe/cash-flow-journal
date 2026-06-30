// ─── Settings Page ───
document.addEventListener('DOMContentLoaded', async () => {
    initSettingsTabs();
    await loadAccountsSettings();
    await loadCategoriesSettings();
    initSettingsFormHandlers();
});

function initSettingsTabs() {
    const tabs = document.querySelectorAll('.settings-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => {
                t.classList.remove('bg-warm-100', 'text-warm-700');
                t.classList.add('text-gray-500', 'hover:bg-warm-50');
            });
            tab.classList.remove('text-gray-500', 'hover:bg-warm-50');
            tab.classList.add('bg-warm-100', 'text-warm-700');

            const tabName = tab.dataset.tab;
            document.querySelectorAll('.settings-content').forEach(c => c.style.display = 'none');
            document.getElementById('content-' + tabName).style.display = 'block';
        });
    });
}

async function loadAccountsSettings() {
    try {
        const accounts = await api('/api/accounts');
        const tbody = document.getElementById('accounts-settings-body');
        if (!tbody) return;
        if (accounts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-gray-400">Belum ada rekening</td></tr>';
            return;
        }
        tbody.innerHTML = accounts.map(a => {
            const balance = (a.opening_balance || 0) + (a.income || 0) - (a.expense || 0);
            return `
                <tr class="border-b border-gray-50 hover:bg-warm-50/50">
                    <td class="py-2.5 font-medium text-gray-700">${esc(a.name)}</td>
                    <td class="py-2.5 text-right text-gray-500">${formatCurrency(a.opening_balance || 0)}</td>
                    <td class="py-2.5 text-right text-green-600">${formatCurrency(a.income || 0)}</td>
                    <td class="py-2.5 text-right text-red-500">${formatCurrency(a.expense || 0)}</td>
                    <td class="py-2.5 text-right font-medium text-gray-700">${formatCurrency(balance)}</td>
                    <td class="py-2.5 text-right">
                        <button onclick="editAccount(${a.id}, '${esc(a.name)}', ${a.opening_balance || 0})" class="text-warm-500 hover:text-warm-700 text-xs font-medium">Edit</button>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (e) {
        console.error('Failed to load accounts:', e);
    }
}

async function loadCategoriesSettings() {
    try {
        const categories = await api('/api/categories');
        const tbody = document.getElementById('categories-settings-body');
        if (!tbody) return;
        if (categories.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-center py-4 text-gray-400">Belum ada kategori</td></tr>';
            return;
        }
        tbody.innerHTML = categories.map(c => `
            <tr class="border-b border-gray-50 hover:bg-warm-50/50">
                <td class="py-2.5 font-medium text-gray-700">${esc(c.name)}</td>
                <td class="py-2.5">
                    <span class="inline-block px-2 py-0.5 text-xs font-medium rounded-full ${c.type === 'income' ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-500'}">${c.type === 'income' ? 'Pemasukan' : 'Pengeluaran'}</span>
                </td>
                <td class="py-2.5 text-right">
                    <button onclick="deleteCategory(${c.id})" class="text-red-400 hover:text-red-600 text-xs font-medium">Hapus</button>
                </td>
            </tr>
        `).join('');
    } catch (e) {
        console.error('Failed to load categories:', e);
    }
}

function initSettingsFormHandlers() {
    // Add account button
    const addAccountBtn = document.getElementById('btn-add-account');
    if (addAccountBtn) {
        addAccountBtn.addEventListener('click', () => {
            document.getElementById('account-id').value = '';
            document.getElementById('account-name').value = '';
            document.getElementById('account-balance').value = '';
            document.getElementById('account-form-title').textContent = 'Tambah Rekening';
            document.getElementById('account-form-modal').style.display = 'flex';
        });
    }

    // Add category button
    const addCategoryBtn = document.getElementById('btn-add-category');
    if (addCategoryBtn) {
        addCategoryBtn.addEventListener('click', () => {
            document.getElementById('category-id').value = '';
            document.getElementById('category-name').value = '';
            document.getElementById('category-type').value = '';
            document.getElementById('category-form-title').textContent = 'Tambah Kategori';
            document.getElementById('category-form-modal').style.display = 'flex';
        });
    }

    // Account form submit
    const accountForm = document.getElementById('account-form');
    if (accountForm) {
        accountForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const id = document.getElementById('account-id').value;
            const data = {
                name: document.getElementById('account-name').value,
                opening_balance: parseFloat(document.getElementById('account-balance').value) || 0
            };
            try {
                if (id) {
                    await api('/api/accounts/' + id, { method: 'PUT', body: JSON.stringify(data) });
                } else {
                    await api('/api/accounts', { method: 'POST', body: JSON.stringify(data) });
                }
                closeAccountForm();
                await loadAccountsSettings();
            } catch (err) {
                alert('Gagal: ' + err.message);
            }
        });
    }

    // Category form submit
    const categoryForm = document.getElementById('category-form');
    if (categoryForm) {
        categoryForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const data = {
                name: document.getElementById('category-name').value,
                type: document.getElementById('category-type').value
            };
            try {
                await api('/api/categories', { method: 'POST', body: JSON.stringify(data) });
                closeCategoryForm();
                await loadCategoriesSettings();
            } catch (err) {
                alert('Gagal: ' + err.message);
            }
        });
    }

    // Delete account button
    const deleteAccountBtn = document.getElementById('btn-delete-account');
    if (deleteAccountBtn) {
        deleteAccountBtn.addEventListener('click', () => {
            document.getElementById('delete-account-modal').style.display = 'flex';
        });
    }

    const confirmDeleteBtn = document.getElementById('confirm-delete-account');
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', async () => {
            try {
                await api('/api/user', { method: 'DELETE' });
                window.location.href = '/login';
            } catch (err) {
                alert('Gagal menghapus: ' + err.message);
            }
        });
    }
}

function closeAccountForm() {
    document.getElementById('account-form-modal').style.display = 'none';
}

function closeCategoryForm() {
    document.getElementById('category-form-modal').style.display = 'none';
}

function closeDeleteAccountModal() {
    document.getElementById('delete-account-modal').style.display = 'none';
}

function editAccount(id, name, balance) {
    document.getElementById('account-id').value = id;
    document.getElementById('account-name').value = name;
    document.getElementById('account-balance').value = balance;
    document.getElementById('account-form-title').textContent = 'Edit Rekening';
    document.getElementById('account-form-modal').style.display = 'flex';
}

async function deleteCategory(id) {
    if (!confirm('Hapus kategori ini?')) return;
    try {
        await api('/api/categories/' + id, { method: 'DELETE' });
        await loadCategoriesSettings();
    } catch (e) {
        alert('Gagal menghapus: ' + e.message);
    }
}
