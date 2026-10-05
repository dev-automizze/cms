<script setup>
import { ref, computed, onMounted } from 'vue'

const API_BASE = window.location.origin.includes('localhost') || window.location.origin.includes('5173') 
  ? 'http://172.20.14.41:5001' 
  : window.location.origin

const pin = ref('')
const isAuthenticated = ref(false)
const errorMessage = ref('')
const printers = ref([])
const isScanning = ref(false)
const collapsedGroups = ref({})

// --- SORTING STATE ---
const sortField = ref('') // 'name' or 'counter'
const sortOrder = ref('asc') // 'asc' or 'desc'

// Modals
const showDeleteModal = ref(false)
const printerToDelete = ref(null)
const showApiModal = ref(false)
const apiKey = ref('')
const copySuccess = ref(false)

const form = ref({
  id: null,
  name: '',
  ip: '',
  brand: 'Generic',
  campus: '', 
  oid: '1.3.6.1.2.1.43.10.2.1.4.1.1',
  purchase_date: ''
})

const isEditing = computed(() => form.value.id !== null)

// Smart HTTP/HTTPS Detection
const isHttps = computed(() => window.location.protocol === 'https:')
const currentOrigin = computed(() => window.location.origin)

// Clean Single API URL Endpoint
const apiUrl = computed(() => {
  return `${currentOrigin.value}/api/export/printers?api_key=${apiKey.value}`
})

// --- SORTED PRINTERS COMPUTED ---
const sortedPrinters = computed(() => {
  if (!sortField.value) {
    return printers.value
  }
  
  return [...printers.value].sort((a, b) => {
    let aVal = sortField.value === 'name' ? a.name : a.last_counter
    let bVal = sortField.value === 'name' ? b.name : b.last_counter
    
    // Handle counter sorting (numbers)
    if (sortField.value === 'counter') {
      aVal = aVal || 0
      bVal = bVal || 0
    }
    
    // Handle string sorting (names)
    if (sortField.value === 'name') {
      aVal = aVal.toLowerCase()
      bVal = bVal.toLowerCase()
    }
    
    if (aVal < bVal) return sortOrder.value === 'asc' ? -1 : 1
    if (aVal > bVal) return sortOrder.value === 'asc' ? 1 : -1
    return 0
  })
})

const groupedPrinters = computed(() => {
  const groups = {}
  sortedPrinters.value.forEach(p => {
    const c = p.campus || 'Ungrouped'
    if (!groups[c]) groups[c] = []
    groups[c].push(p)
  })
  return groups
})

// --- UI STATE PERSISTENCE ---
const COLLAPSE_KEY = 'cms_collapsed_groups'

function toggleGroup(campus) {
  collapsedGroups.value[campus] = !collapsedGroups.value[campus]
  localStorage.setItem(COLLAPSE_KEY, JSON.stringify(collapsedGroups.value))
}

function loadCollapsedState() {
  const savedState = localStorage.getItem(COLLAPSE_KEY)
  if (savedState) {
    try {
      collapsedGroups.value = JSON.parse(savedState)
    } catch (err) {
      console.error("Could not load saved group states.")
    }
  }
}

// --- AUTHENTICATION ---
const AUTH_KEY = 'cms_auth_time'
const EIGHT_HOURS = 8 * 60 * 60 * 1000

function checkSession() {
  const savedTime = localStorage.getItem(AUTH_KEY)
  if (savedTime && (Date.now() - parseInt(savedTime)) < EIGHT_HOURS) {
    isAuthenticated.value = true
    loadDashboard()
  } else {
    localStorage.removeItem(AUTH_KEY)
    isAuthenticated.value = false
  }
}

async function handleLogin() {
  errorMessage.value = ''
  try {
    const res = await fetch(`${API_BASE}/api/verify-pin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: pin.value })
    })
    
    if (res.ok) {
      localStorage.setItem(AUTH_KEY, Date.now().toString())
      isAuthenticated.value = true
      loadDashboard()
    } else {
      errorMessage.value = 'Invalid PIN. Try again.'
    }
  } catch (err) {
    errorMessage.value = 'Cannot connect to backend.'
  }
}

// --- DASHBOARD DATA ---
function loadDashboard() {
  fetchPrinters()
  fetchApiKey()
}

async function fetchPrinters() {
  try {
    const res = await fetch(`${API_BASE}/api/printers`)
    printers.value = await res.json()
  } catch (err) {
    console.error('Failed to load printers:', err)
  }
}

async function triggerScan() {
  isScanning.value = true
  try {
    await fetch(`${API_BASE}/api/counters/scan`)
    await fetchPrinters() 
  } catch (err) {
    console.error('Scan failed:', err)
  } finally {
    isScanning.value = false
  }
}

// --- SORTING FUNCTIONS ---
function toggleSort(field) {
  if (sortField.value === field) {
    // Toggle order if same field
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    // New field, set to ascending
    sortField.value = field
    sortOrder.value = 'asc'
  }
}

function getSortIcon(field) {
  if (sortField.value !== field) return '↕'
  return sortOrder.value === 'asc' ? '↑' : '↓'
}

// --- API KEY LOGIC ---
async function fetchApiKey() {
  try {
    const res = await fetch(`${API_BASE}/api/settings/api-key`)
    const data = await res.json()
    apiKey.value = data.api_key
  } catch (err) {
    console.error('Failed to fetch API key:', err)
  }
}

async function regenerateKey() {
  if(!confirm("Warning: Generating a new API key will break your existing integrations. Continue?")) return;
  try {
    const res = await fetch(`${API_BASE}/api/settings/api-key/regenerate`, { method: 'POST' })
    const data = await res.json()
    apiKey.value = data.api_key
  } catch (err) {
    console.error('Failed to regenerate key:', err)
  }
}

async function copyCode() {
  try {
    await navigator.clipboard.writeText(apiUrl.value)
    copySuccess.value = true
    setTimeout(() => copySuccess.value = false, 2000)
  } catch (err) {
    alert("Failed to copy URL. Please select and copy manually.")
  }
}

// --- PRINTER CRUD ---
async function savePrinter() {
  if (!form.value.name || !form.value.ip) return
  
  const url = isEditing.value ? `${API_BASE}/api/printers/${form.value.id}` : `${API_BASE}/api/printers`
  const method = isEditing.value ? 'PUT' : 'POST'
  
  try {
    const res = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value)
    })
    if (res.ok) {
      cancelEdit()
      fetchPrinters()
    }
  } catch (err) {
    console.error('Failed to save printer:', err)
  }
}

function promptDelete(id) {
  printerToDelete.value = id
  showDeleteModal.value = true
}

function cancelDelete() {
  showDeleteModal.value = false
  printerToDelete.value = null
}

async function confirmDelete() {
  if (!printerToDelete.value) return
  try {
    const res = await fetch(`${API_BASE}/api/printers/${printerToDelete.value}`, { method: 'DELETE' })
    if (res.ok) fetchPrinters()
  } catch (err) {
    console.error('Failed to delete printer:', err)
  } finally {
    showDeleteModal.value = false
    printerToDelete.value = null
  }
}

function editPrinter(p) {
  form.value = { ...p }
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function cancelEdit() {
  form.value = { id: null, name: '', ip: '', brand: 'Generic', campus: '', oid: '1.3.6.1.2.1.43.10.2.1.4.1.1', purchase_date: '' }
}

onMounted(() => {
  checkSession()
  loadCollapsedState()
})
</script>

<template>
  <div class="app-wrapper">
    <div class="cms-container">
      
      <!-- PIN LOCK SCREEN -->
      <div v-if="!isAuthenticated" class="auth-wrapper">
        <div class="card pin-card">
          <div class="icon-lock">🖨️</div>
          <h2>CMS Login</h2>
          <p class="subtitle">Enter access PIN</p>
          <input 
            v-model="pin" 
            type="password" 
            maxlength="4" 
            placeholder="••••" 
            @keyup.enter="handleLogin"
            class="pin-input"
          />
          <button @click="handleLogin" class="btn-primary full-width">Unlock Dashboard</button>
          <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
        </div>
      </div>

      <!-- MAIN DASHBOARD -->
      <div v-else class="dashboard">
        <header class="header">
          <div>
            <h1>Counter Management Solution</h1>
            <p class="subtitle">Lazy to update your printer counter each month? Try me.</p>
          </div>
          <div class="header-actions">
            <button class="btn-secondary" @click="showApiModal = true">⚙️ Generate API Key</button>
            <button class="btn-scan" :disabled="isScanning" @click="triggerScan">
              <span v-if="isScanning">⏳ Updating...</span>
              <span v-else>⚡ Update Counters Now</span>
            </button>
          </div>
        </header>

        <!-- PRINTER FORM -->
        <div class="card form-card">
          <h3>{{ isEditing ? 'Edit Printer' : 'Add New Printer' }}</h3>
          <div class="form-grid">
            <div class="input-group">
              <label>Group Name</label>
              <input v-model="form.campus" placeholder="e.g. TK, TTP..." />
            </div>
            <div class="input-group">
              <label>Location / Name</label>
              <input v-model="form.name" placeholder="e.g. Staffroom L3250" />
            </div>
            <div class="input-group">
              <label>IP Address</label>
              <input v-model="form.ip" placeholder="172.20.x.x" />
            </div>
            <div class="input-group">
              <label>Brand</label>
              <select v-model="form.brand">
                <option value="Generic">Generic</option>
                <option value="Epson">Epson</option>
                <option value="HP">HP</option>
                <option value="Canon">Canon</option>
              </select>
            </div>
            <div class="input-group">
              <label>Purchase Date</label>
              <input type="date" v-model="form.purchase_date" />
            </div>
            <div class="form-actions">
              <button @click="savePrinter" class="btn-primary">
                {{ isEditing ? 'Save' : 'Add' }}
              </button>
              <button v-if="isEditing" @click="cancelEdit" class="btn-secondary">Cancel</button>
            </div>
          </div>
        </div>

        <div v-if="Object.keys(groupedPrinters).length === 0" class="card empty-card">
          <p class="empty">No printers added yet.</p>
        </div>

        <div v-for="(printerList, campus) in groupedPrinters" :key="campus" class="group-wrapper">
          <div class="group-header" @click="toggleGroup(campus)">
            <div class="group-title">
              <h3>📁 {{ campus }}</h3>
              <span class="badge-count">{{ printerList.length }}</span>
            </div>
            <div class="toggle-icon">
              {{ collapsedGroups[campus] ? '▼' : '▲' }}
            </div>
          </div>
          
          <div class="card table-card" v-show="!collapsedGroups[campus]">
            <table>
              <thead>
                <tr>
                  <th 
                    @click="toggleSort('name')" 
                    class="sortable-header"
                    :class="{ 'active-sort': sortField === 'name' }"
                  >
                    <span>Location / Name</span>
                    <span class="sort-icon">{{ getSortIcon('name') }}</span>
                  </th>
                  <th>IP Address</th>
                  <th>Brand</th>
                  <th 
                    @click="toggleSort('counter')" 
                    class="sortable-header"
                    :class="{ 'active-sort': sortField === 'counter' }"
                  >
                    <span>Total Counter</span>
                    <span class="sort-icon">{{ getSortIcon('counter') }}</span>
                  </th>
                  <th>Last Synced</th>
                  <th class="actions-col">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="p in printerList" :key="p.id">
                  <td>
                    <div style="display: flex; flex-direction: column;">
                      <strong>{{ p.name }}</strong>
                      <span v-if="p.purchase_date" class="purchase-date-text">
                        Purchased: {{ p.purchase_date }}
                      </span>
                    </div>
                  </td>
                  <td><span class="ip-badge">{{ p.ip }}</span></td>
                  <td><span class="brand-badge">{{ p.brand }}</span></td>
                  <td class="counter">{{ p.last_counter || '---' }}</td>
                  <td class="timestamp">{{ p.last_updated || 'Never' }}</td>
                  <td class="actions-col">
                    <button @click="editPrinter(p)" class="btn-text edit">Edit</button>
                    <button @click="promptDelete(p.id)" class="btn-text danger">Delete</button>
                  </td>
                </tr>
                <tr v-if="printerList.length === 0">
                  <td colspan="6" class="no-results">No printers in this group</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
      
      <!-- API GENERATOR MODAL -->
      <div v-if="showApiModal" class="modal-overlay">
        <div class="modal-card code-modal">
          <h3 class="modal-title">API Key Integration</h3>
          <p class="modal-instruction">Use this direct endpoint URL to fetch live printer data into Google Sheets or external services.</p>

          <div class="api-url-container">
            <input 
              type="text" 
              readonly 
              :value="apiUrl" 
              class="url-input" 
            />
            <button @click="copyCode" class="btn-primary btn-copy">
              {{ copySuccess ? '✅ Copied!' : '📋 Copy URL' }}
            </button>
          </div>

          <p class="sub-instruction">
            🔒 Keep this key private. Anyone with this link can view your counter exports.
          </p>

          <div class="api-key-controls">
             <button @click="regenerateKey" class="btn-text danger text-small">↻ Regenerate API Key</button>
             <span class="hint">Warning: Breaks existing sheets/integrations.</span>
          </div>

          <div class="modal-actions mt-4">
            <button @click="showApiModal = false" class="btn-secondary full-width">Close</button>
          </div>
        </div>
      </div>

      <!-- CUSTOM DELETE MODAL -->
      <div v-if="showDeleteModal" class="modal-overlay">
        <div class="modal-card">
          <div class="modal-icon">⚠️</div>
          <h3 class="modal-title">Confirm Deletion</h3>
          <p class="modal-text">Are you sure you want to delete this printer? This action cannot be undone.</p>
          <div class="modal-actions">
            <button @click="cancelDelete" class="btn-secondary">Cancel</button>
            <button @click="confirmDelete" class="btn-danger">Delete</button>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<style>
:root {
  --bg-main: #FEE7C8;
  --primary: #722F99;
  --primary-hover: #5A257A;
  --card-bg: #FFFFFF;
  --text-main: #2D1A3D;
  --text-muted: #6B5B7B;
  --border-color: #EADCF2;
  --input-bg: #FDFBFF;
  --danger: #D32F2F;
  --danger-hover: #B71C1C;
}

html, body { margin: 0; padding: 0; background-color: var(--bg-main) !important; color: var(--text-main) !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; height: 100%; }
* { box-sizing: border-box; }
.app-wrapper { min-height: 100vh; background-color: var(--bg-main); padding: 40px 20px; }
.cms-container { max-width: 1050px; margin: 0 auto; }
.card { background-color: var(--card-bg) !important; border: 1px solid var(--border-color); border-radius: 12px; padding: 24px; margin-bottom: 24px; box-shadow: 0 4px 15px rgba(114, 47, 153, 0.05); }
.auth-wrapper { display: flex; justify-content: center; align-items: center; min-height: 70vh; }
.pin-card { width: 100%; max-width: 360px; text-align: center; }
.icon-lock { font-size: 40px; margin-bottom: 12px; }
.pin-input { width: 100%; font-size: 24px; letter-spacing: 12px; text-align: center; margin: 20px 0; padding: 12px; border-radius: 8px; border: 2px solid var(--border-color); background-color: var(--input-bg); color: var(--text-main); }
.pin-input:focus { border-color: var(--primary); outline: none; }
h1 { font-size: 28px; font-weight: 700; margin: 0 0 4px 0; color: var(--primary); }
h2 { font-size: 24px; font-weight: 700; margin: 0 0 4px 0; color: var(--primary); }
h3 { font-size: 18px; font-weight: 600; margin: 0 0 16px 0; color: var(--text-main); }
.subtitle { color: var(--text-muted); font-size: 15px; margin: 0; }
input, select { width: 100%; padding: 10px 12px; background-color: var(--input-bg); border: 1px solid var(--border-color); color: var(--text-main); border-radius: 6px; font-size: 14px; outline: none; transition: border-color 0.2s; }
input:focus, select:focus { border-color: var(--primary); background-color: #fff; }
button { font-family: inherit; font-size: 14px; font-weight: 600; border-radius: 6px; border: none; cursor: pointer; padding: 10px 18px; transition: all 0.2s; }
.btn-primary { background-color: var(--primary); color: #fff; }
.btn-primary:hover { background-color: var(--primary-hover); transform: translateY(-1px); }
.btn-secondary { background-color: #F0E6F5; color: var(--text-main); border: 1px solid var(--border-color); }
.btn-secondary:hover { background-color: #E2D4EB; }
.btn-danger { background-color: var(--danger); color: #fff; }
.btn-danger:hover { background-color: var(--danger-hover); }
.btn-scan { background-color: var(--primary); color: #fff; padding: 12px 24px; box-shadow: 0 4px 12px rgba(114, 47, 153, 0.2); }
.btn-scan:hover:not(:disabled) { background-color: var(--primary-hover); }
.btn-scan:disabled { opacity: 0.7; cursor: not-allowed; }
.full-width { width: 100%; padding: 12px; }
.form-grid { 
  display: grid; 
  grid-template-columns: 1fr 1.5fr 1.5fr 1fr 1fr auto; 
  gap: 16px; 
  align-items: end; 
}
.purchase-date-text {
  font-size: 11.5px;
  color: var(--text-muted);
  margin-top: 2px;
}
.input-group label { display: block; font-size: 12px; font-weight: 700; color: var(--primary); margin-bottom: 6px; text-transform: uppercase; }
.form-actions { display: flex; gap: 8px; }
.group-wrapper { margin-bottom: 24px; }
.group-header { display: flex; justify-content: space-between; align-items: center; cursor: pointer; padding: 14px 20px; background-color: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; margin-bottom: 8px; box-shadow: 0 2px 8px rgba(114, 47, 153, 0.04); }
.group-title { display: flex; align-items: center; gap: 12px; }
.group-title h3 { margin: 0; font-size: 16px; color: var(--primary); }
.badge-count { background-color: var(--primary); color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: bold; }
.toggle-icon { color: var(--primary); font-size: 12px; font-weight: bold; }
.table-card { padding: 0; overflow: hidden; background-color: var(--card-bg); }
table { width: 100%; border-collapse: collapse; background-color: var(--card-bg); }
th { background-color: #FAF5FF; padding: 14px 20px; font-size: 13px; font-weight: 700; color: var(--primary); text-transform: uppercase; text-align: left; border-bottom: 2px solid var(--border-color); }
td { padding: 16px 20px; border-bottom: 1px solid var(--border-color); font-size: 14px; color: var(--text-main); background-color: var(--card-bg); }
tr:hover td { background-color: #FDFBFF; }
.counter { font-weight: 700; color: var(--primary); font-size: 16px; }
.ip-badge, .brand-badge { background-color: #F0E6F5; color: var(--text-main); padding: 4px 8px; border-radius: 6px; font-family: monospace; font-size: 13px; }
.actions-col { text-align: right; }
.btn-text { background: transparent; font-weight: 600; padding: 6px 10px; }
.btn-text.edit { color: var(--primary); }
.btn-text.edit:hover { background: #F0E6F5; }
.btn-text.danger { color: var(--danger); }
.btn-text.danger:hover { background: #FFEBEE; }
.empty { text-align: center; color: var(--text-muted); padding: 30px; font-style: italic; }
.error { color: var(--danger); font-size: 14px; margin-top: 12px; font-weight: 600; }
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background-color: rgba(45, 26, 61, 0.7); display: flex; justify-content: center; align-items: center; z-index: 1000; backdrop-filter: blur(4px); }
.modal-card { background-color: var(--card-bg) !important; border-radius: 12px; padding: 30px; max-width: 400px; width: 90%; text-align: center; box-shadow: 0 15px 30px rgba(0, 0, 0, 0.3); }
.code-modal { max-width: 600px; text-align: left; }
.modal-icon { font-size: 40px; margin-bottom: 16px; }
.modal-title { color: var(--text-main); margin-bottom: 12px; font-size: 20px; font-weight: bold; }
.modal-text { color: var(--text-muted); margin-bottom: 24px; line-height: 1.5; }
.modal-actions { display: flex; justify-content: center; gap: 12px; }
.header-actions { display: flex; gap: 12px; align-items: center; }
.timestamp { font-size: 12px; color: var(--text-muted); }
.mt-4 { margin-top: 20px; }
.hint { font-size: 12px; color: var(--text-muted); }
.text-small { font-size: 12px; padding: 4px 8px; }

/* Simplified API URL Field Styling */
.modal-instruction { font-size: 14px; color: var(--text-muted); margin-bottom: 16px; }
.sub-instruction { font-size: 12px; color: var(--text-muted); margin: 12px 0 20px 0; background: #FFF8E1; border: 1px solid #FFE082; padding: 8px 12px; border-radius: 6px; }
.api-url-container { display: flex; gap: 8px; margin-bottom: 8px; }
.url-input { flex: 1; font-family: monospace; font-size: 13px; color: var(--primary); font-weight: 600; background-color: #FDFBFF; }
.btn-copy { whitespace: nowrap; }
.api-key-controls { display: flex; justify-content: space-between; align-items: center; padding-top: 8px; border-top: 1px border-style var(--border-color); }

/* --- SORTING STYLES --- */
.sortable-header {
  cursor: pointer;
  user-select: none;
  transition: background-color 0.2s;
  position: relative;
}

.sortable-header:hover {
  background-color: #E8D5F0;
}

.sortable-header span {
  display: inline-block;
}

.sort-icon {
  margin-left: 8px;
  font-size: 14px;
  color: var(--primary);
  opacity: 0.5;
  display: inline-block;
}

.sortable-header:hover .sort-icon {
  opacity: 1;
}

.sortable-header.active-sort {
  background-color: #E8D5F0;
}

.sortable-header.active-sort .sort-icon {
  opacity: 1;
}

@media (max-width: 800px) { 
  .form-grid { grid-template-columns: 1fr; gap: 12px; } 
  .header { flex-direction: column; gap: 16px; align-items: flex-start; } 
  .api-url-container { flex-direction: column; }
}
@media (max-width: 900px) { 
  .form-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 600px) { 
  .form-grid { grid-template-columns: 1fr; }
}
</style>
