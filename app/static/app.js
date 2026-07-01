// ─── Debt Buttons Section ───
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
                    ${d.status === 'paid' ? '' : `<button class="btn-circle btn-circle-success" onclick="openPayModal(${d.id})" aria-label="Bayar hutang" title="Bayar hutang"></button>`}
                    <button class="btn-circle btn-circle-danger" onclick="deleteDebt(${d.id})" aria-label="Hapus hutang" title="Hapus hutang"></button>
                </td>
            </tr>
        `;
    }).join('');
}