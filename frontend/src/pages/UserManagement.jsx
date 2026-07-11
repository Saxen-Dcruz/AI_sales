import { useState, useEffect } from 'react'
import { Navigate } from 'react-router-dom'
import { Shield, Plus, Pencil, Key, X, Check, Loader2, Mail, Eye, EyeOff } from 'lucide-react'
import ApplicationStore from '../utils/ApplicationStore'
import {
  ListUsersService, CreateUserService, UpdateUserService,
} from '../services/ApiService'

function isSuperAdmin() {
  const { userDetails } = ApplicationStore().getStorage('userDetails') || {}
  return userDetails?.userRole === 'Admin'
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 bg-gray-50">
          <h2 className="text-sm font-bold text-gray-900">{title}</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-200 text-gray-400 transition-all">
            <X size={15} />
          </button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{label}</label>
      {children}
    </div>
  )
}

const inputCls = "w-full text-sm border border-gray-200 rounded-xl px-3 py-2 focus:outline-none focus:border-indigo-400 transition-all"

function PasswordInput({ value, onChange, placeholder }) {
  const [show, setShow] = useState(false)
  return (
    <div className="relative">
      <input type={show ? 'text' : 'password'} className={`${inputCls} pr-10`}
        placeholder={placeholder} value={value} onChange={onChange} />
      <button type="button" onClick={() => setShow(s => !s)} tabIndex={-1}
        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors">
        {show ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  )
}

export default function UserManagement() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState(null) // 'create' | 'edit' | 'password' | null
  const [selected, setSelected] = useState(null)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState(null)

  const [form, setForm] = useState({ email: '', password: '', is_superuser: false })
  const [pwForm, setPwForm] = useState({ password: '' })

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const fetchUsers = () => {
    setLoading(true)
    ListUsersService(
      (data) => { setUsers(Array.isArray(data) ? data : []); setLoading(false) },
      () => setLoading(false)
    )
  }

  useEffect(() => { fetchUsers() }, [])

  if (!isSuperAdmin()) return <Navigate to="/dashboard" replace />

  const openCreate = () => {
    setForm({ email: '', password: '', is_superuser: false })
    setSelected(null)
    setModal('create')
  }

  const openEdit = (u) => {
    setSelected(u)
    setForm({ email: u.email, is_superuser: u.is_superuser, password: '' })
    setModal('edit')
  }

  const openPassword = (u) => {
    setSelected(u)
    setPwForm({ password: '' })
    setModal('password')
  }

  const closeModal = () => { setModal(null); setSelected(null) }

  const handleCreate = () => {
    if (!form.email || !form.password) return showToast('Email and password required', 'error')
    setSaving(true)
    CreateUserService(
      { email: form.email, password: form.password, is_superuser: form.is_superuser },
      () => { setSaving(false); closeModal(); fetchUsers(); showToast(`${form.email} created`) },
      (_, msg) => { setSaving(false); showToast(msg || 'Create failed', 'error') }
    )
  }

  const handleEdit = () => {
    setSaving(true)
    const payload = { is_superuser: form.is_superuser, is_active: selected.is_active }
    if (form.password) payload.password = form.password
    UpdateUserService(selected.id, payload,
      () => { setSaving(false); closeModal(); fetchUsers(); showToast('User updated') },
      (_, msg) => { setSaving(false); showToast(msg || 'Update failed', 'error') }
    )
  }

  const handleResetPassword = () => {
    if (!pwForm.password) return showToast('New password required', 'error')
    setSaving(true)
    UpdateUserService(selected.id, { password: pwForm.password },
      () => { setSaving(false); closeModal(); showToast('Password reset') },
      (_, msg) => { setSaving(false); showToast(msg || 'Reset failed', 'error') }
    )
  }

  const handleToggleActive = (u) => {
    UpdateUserService(u.id, { is_active: !u.is_active },
      () => { fetchUsers(); showToast(`${u.email} ${!u.is_active ? 'activated' : 'deactivated'}`) },
      (_, msg) => showToast(msg || 'Update failed', 'error')
    )
  }

  // Filter out test/fixture accounts so the admin sees only real users
  const realUsers = users.filter(u =>
    !u.email.includes('@rdltest.com') && !u.email.includes('auth_') && !u.email.includes('test_')
  )

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {toast && (
        <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-xl text-sm font-semibold shadow-lg
          ${toast.type === 'error' ? 'bg-red-600 text-white' : 'bg-emerald-600 text-white'}`}>
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Shield size={22} className="text-violet-600" />
            User Management
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Manage team accounts, roles and access — super-admin only
          </p>
        </div>
        <button onClick={openCreate}
          className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white text-sm font-semibold rounded-xl hover:bg-violet-700 transition-all">
          <Plus size={14} /> Add User
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16 gap-3 text-gray-400">
            <Loader2 size={20} className="animate-spin" /> Loading users…
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                {['Email', 'Gmail Account', 'Role', 'Status', 'Actions'].map(h => (
                  <th key={h} className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {realUsers.map(u => (
                <tr key={u.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-5 py-3.5 font-medium text-gray-900">{u.email}</td>
                  <td className="px-5 py-3.5">
                    {(u.gmail_accounts || []).length === 0 ? (
                      <span className="text-[10px] text-gray-400 italic">No account linked</span>
                    ) : (u.gmail_accounts || []).map(a => (
                      <span key={a.id}
                        className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full mr-1
                          ${a.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
                        <Mail size={8} />
                        {a.email_address}
                        {!a.auto_send_enabled && <span className="ml-0.5 text-amber-600">✋</span>}
                      </span>
                    ))}
                  </td>
                  <td className="px-5 py-3.5">
                    {u.is_superuser ? (
                      <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-violet-100 text-violet-700">
                        <Shield size={9} /> SUPER ADMIN
                      </span>
                    ) : (
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                        USER
                      </span>
                    )}
                  </td>
                  <td className="px-5 py-3.5">
                    <button onClick={() => handleToggleActive(u)}
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full transition-all
                        ${u.is_active ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200' : 'bg-red-100 text-red-600 hover:bg-red-200'}`}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </button>
                  </td>
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-1.5">
                      <button onClick={() => openEdit(u)} title="Edit role"
                        className="p-1.5 rounded-lg text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 transition-all">
                        <Pencil size={13} />
                      </button>
                      <button onClick={() => openPassword(u)} title="Reset password"
                        className="p-1.5 rounded-lg text-gray-400 hover:text-amber-600 hover:bg-amber-50 transition-all">
                        <Key size={13} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {realUsers.length === 0 && (
                <tr><td colSpan={5} className="px-5 py-10 text-center text-sm text-gray-400">No users found</td></tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Create modal */}
      {modal === 'create' && (
        <Modal title="Add User" onClose={closeModal}>
          <div className="space-y-4">
            <Field label="Email">
              <input type="email" className={inputCls} placeholder="user@rdltech.in"
                value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
            </Field>
            <Field label="Password">
              <PasswordInput placeholder="Min 6 characters"
                value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
            </Field>
            <Field label="Role">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.is_superuser}
                  onChange={e => setForm({ ...form, is_superuser: e.target.checked })}
                  className="accent-violet-600 w-4 h-4" />
                <span className="text-sm text-gray-700">Super Admin</span>
              </label>
            </Field>
            <div className="flex gap-2 pt-2">
              <button onClick={closeModal}
                className="flex-1 py-2 rounded-xl border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition-all">
                Cancel
              </button>
              <button onClick={handleCreate} disabled={saving}
                className="flex-1 py-2 rounded-xl bg-violet-600 text-white text-sm font-semibold hover:bg-violet-700 transition-all disabled:opacity-50 flex items-center justify-center gap-1.5">
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                Create
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Edit modal */}
      {modal === 'edit' && selected && (
        <Modal title={`Edit — ${selected.email}`} onClose={closeModal}>
          <div className="space-y-4">
            <Field label="Role">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={form.is_superuser}
                  onChange={e => setForm({ ...form, is_superuser: e.target.checked })}
                  className="accent-violet-600 w-4 h-4" />
                <span className="text-sm text-gray-700">Super Admin</span>
              </label>
            </Field>
            <Field label="Force new password (optional)">
              <PasswordInput placeholder="Leave blank to keep current"
                value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} />
            </Field>
            <div className="flex gap-2 pt-2">
              <button onClick={closeModal}
                className="flex-1 py-2 rounded-xl border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition-all">
                Cancel
              </button>
              <button onClick={handleEdit} disabled={saving}
                className="flex-1 py-2 rounded-xl bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 transition-all disabled:opacity-50 flex items-center justify-center gap-1.5">
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                Save
              </button>
            </div>
          </div>
        </Modal>
      )}

      {/* Password reset modal */}
      {modal === 'password' && selected && (
        <Modal title={`Reset password — ${selected.email}`} onClose={closeModal}>
          <div className="space-y-4">
            <Field label="New password">
              <PasswordInput placeholder="Min 6 characters"
                value={pwForm.password} onChange={e => setPwForm({ password: e.target.value })} />
            </Field>
            <div className="flex gap-2 pt-2">
              <button onClick={closeModal}
                className="flex-1 py-2 rounded-xl border border-gray-200 text-sm text-gray-600 hover:bg-gray-50 transition-all">
                Cancel
              </button>
              <button onClick={handleResetPassword} disabled={saving}
                className="flex-1 py-2 rounded-xl bg-amber-600 text-white text-sm font-semibold hover:bg-amber-700 transition-all disabled:opacity-50 flex items-center justify-center gap-1.5">
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Key size={14} />}
                Reset
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
