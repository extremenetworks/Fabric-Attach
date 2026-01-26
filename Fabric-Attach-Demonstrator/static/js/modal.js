// ----------------------------------------------------------------------------------------------------
// VLAN delete modal
// ----------------------------------------------------------------------------------------------------
const deleteModalElement = document.getElementById('delete-modal')
const deleteModal = new Modal(deleteModalElement, { closable: false }, {})

// callback to delete VLAN
deleteModalElement.querySelector('[data-vlan-id]').addEventListener('click', async (e) => {
    const vlanId = e.target.getAttribute('data-vlan-id')

    const response = await fetch('/config', {
        method: 'DELETE',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            'vlanId': vlanId
        })
    })

    if (response.ok) {
        // hide modal on success
        deleteModal.hide()
    } else {
        // show error message on failure
        const json = await response.json()
        createToast(json.msg, 'error', 10000)

        // debug:
        console.debug(`cannot delete VLAN ${vlanId}:`, json)
    }
})

// ----------------------------------------------------------------------------------------------------
// LLDP edit modal
// ----------------------------------------------------------------------------------------------------
const llpdModalElement = document.getElementById('lldp-modal')
const lldpModal = new Modal(llpdModalElement, { closable: false }, {})

// save changes of LLDP config
lldpForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const response = await fetch('/config', {
        method: 'PATCH',
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(getLLDPForm())
    })

    if (response.ok) {
        // hide modal on success
        lldpModal.hide()
    } else {
        // show error message on failure
        const json = await response.json()
        createToast(json.msg, 'error', 10000)

        // debug:
        console.debug('cannot update LLDP config:', json)
    }
})

// ----------------------------------------------------------------------------------------------------
// VLAN edit modal
// ----------------------------------------------------------------------------------------------------
const vlanModalElement = document.getElementById('vlan-modal')
const vlanModal = new Modal(vlanModalElement, { closable: false }, {})

// create / update VLAN
vlanForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    // get data from form
    const data = getVLANForm()

    const response = await fetch('/config', {
        method: vlanForm.getAttribute('data-method'),
        headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })

    if (response.ok) {
        // hide modal on success
        vlanModal.hide()
    } else {
        // show error message on failure
        const json = await response.json()
        createToast(json.msg, 'error', 10000)

        // debug:
        console.debug('cannot update LLDP config:', json)
    }
})
