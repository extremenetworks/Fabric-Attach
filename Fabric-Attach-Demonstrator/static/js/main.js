const host = location.origin
const socket = io.connect(host)

// ----------------------------------------------------------------------------------------------------
// Socket IO callbacks
// ----------------------------------------------------------------------------------------------------

// --------------------------------------------------
// Connect
// --------------------------------------------------
// debug:
socket.on('connect', function () {
    console.debug(`connected to websocket server at ${host}`)
})

// --------------------------------------------------
// LLDP inbound / outbound
// --------------------------------------------------
for (const type of ['inbound', 'outbound']) {
    socket.on(type, function (msg) {
        const json = JSON.parse(msg.data)
        const table = document.querySelector(`[data-name=lldp-${type}]`)

        // debug:
        console.debug(`got data of type: ${type}:`, json)

        // create LLDP table elements
        createLLDPTable(table, json, type)
    })
}

// --------------------------------------------------
// Config (contains VM data)
// --------------------------------------------------
socket.on('config', function (msg) {
    const json = JSON.parse(msg.data)

    // debug:
    console.debug('got config data:', json)

    // clear all present VLANs in the table
    clearTable()

    // repopulate table with incoming VLANs
    for (const vlan of Object.values(json)) {
        displayVLAN(vlan)
    }
})

// --------------------------------------------------
// State (contains VM state)
// --------------------------------------------------
socket.on('state', function (msg) {
    const json = JSON.parse(msg.data)

    // debug:
    console.debug('got state data:', json)

    for (const [id, state] of Object.entries(json)) {
        setVLANState(id, state)
    }
})

// --------------------------------------------------
// Response
// --------------------------------------------------
socket.on('response', function (msg) {
    // debug:
    console.debug('got response:', msg)

    // determine type of response
    const type = msg.data.success === false ? 'error' : 'success'

    // if message contains data create a notification
    if (msg.data.message) {
        // create notification and append to parent
        createToast(msg.data.message, type, 10000)
    }
})


// ----------------------------------------------------------------------------------------------------
// EventListeners
// ----------------------------------------------------------------------------------------------------
const createVlanBtn = document.querySelector('button[data-name=create-new]')
createVlanBtn.addEventListener('click', _ => {
    // set form method to POST
    vlanForm.setAttribute('data-method', 'POST')

    // clear previous data from VLAN form (if present)
    clearVLANForm()

    // show VLAN-modal with empty form
    vlanModal.show()
})

async function actionEventHandler(action) {
    // send request
    const response = await fetch(new URL('/control', host), {
        method: 'POST',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            'action': action
        })
    })

    // if request fails show error message
    if (!response.ok) {
        createToast(`Could not perform action ${action}!`, 'error')
        return
    }

    // show success message
    const json = await response.json()
    createToast(json.message, 'success')
}

const shutdownBtn = document.querySelector('button[data-name=shutdown]')
shutdownBtn.addEventListener('click', _ => actionEventHandler('shutdown'))

const rebootBtn = document.querySelector('button[data-name=reboot]')
rebootBtn.addEventListener('click', _ => actionEventHandler('reboot'))

const resetBtn = document.querySelector('button[data-name=reset]')
resetBtn.addEventListener('click', _ => {
    actionEventHandler('reset').then(_ =>
        // reload page after 2 seconds
        setTimeout(_ => location.reload(), 2000)
    )
})