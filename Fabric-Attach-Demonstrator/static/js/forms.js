// ----------------------------------------------------------------------------------------------------
// VLAN
// ----------------------------------------------------------------------------------------------------
// style input field as disabled
function disableInput(input) {
    input.disabled = true

    input.classList.remove('bg-gray-50')
    input.classList.add('bg-gray-300')
}

// style input field as enabled
function enableInput(input) {
    input.disabled = false

    input.classList.add('bg-gray-50')
    input.classList.remove('bg-gray-300')
}

// add input field for ip address
function addPingAddr(value) {
    // get element from template
    const template = vlanForm.querySelector('template#ping-add-input')
    const pingInput = template.content.cloneNode(true).firstElementChild

    // fill input field
    pingInput.querySelector('input').value = value

    // add event listener to remove element
    pingInput.querySelector('button').addEventListener('click', _ => {
        pingInput.remove()
    })

    // add element to form
    const pingWrapper = vlanForm.querySelector('div#ping')
    pingWrapper.appendChild(pingInput)
}

const vlanForm = document.querySelector('form#vlan-update-form')

// disable ip, dgw input if dhcp is enabled
const dhcpCheckbox = vlanForm.querySelector('input#dhcp')
dhcpCheckbox.addEventListener('change', _ => {
    const inputs = vlanForm.querySelectorAll('input#ip, input#dgw')

    if (dhcpCheckbox.checked) {
        inputs.forEach(disableInput)
    } else {
        inputs.forEach(enableInput)
    }
})

// onclick callback to add new empty fields
const addAddrBtn = vlanForm.querySelector('button#add-addr-btn')
addAddrBtn.addEventListener('click', (e) => {
    e.stopImmediatePropagation()
    e.preventDefault()

    // add empty input field
    addPingAddr('')
})

// fill VLAN form with given data
function fillVLANForm(vlan) {
    // fill form fields with values
    vlanForm.querySelector('input#vlanId').value = vlan.vlanId
    vlanForm.querySelector('input#isid').value = vlan.isid

    // reset dhcp field to unchecked
    // note: this is handled by the event listener of the checkbox
    vlanForm.querySelector('input#dhcp').checked = true
    vlanForm.querySelector('input#dhcp').click() // dhcp is now off

    if (vlan.dhcp) {
        vlanForm.querySelector('input#dhcp').click()
    }

    vlanForm.querySelector('input#iperf').checked = vlan.iperf
    vlanForm.querySelector('input#web').checked = vlan.web

    vlanForm.querySelector('input#ip').value = vlan.ip
    vlanForm.querySelector('input#dgw').value = vlan.dgw

    vlanForm.querySelector('input#mcast-client').value = vlan.mcast.client
    vlanForm.querySelector('input#mcast-server').value = vlan.mcast.server

    // clear ping address fields
    const pingWrapper = vlanForm.querySelector('div#ping')
    pingWrapper.innerHTML = ''

    // only add address fields if 'addr' string is not empty
    for (const addr of vlan.ping) {
        if (addr)
            addPingAddr(addr)
    }
}

// clear VLAN form
function clearVLANForm() {
    fillVLANForm({
        vlanId: '',
        isid: '',
        dhcp: false,
        iperf: false,
        web: false,
        ip: '',
        dgw: '',
        ping: [],
        mcast: {
            client: '',
            server: ''
        }
    })
}

// get input values of the VLAN form and return a dictionary
function getVLANForm() {
    // get all input values from the address input fields of the modal form
    const nodeList = vlanForm.querySelector('#ping').querySelectorAll('input')

    // convert NodeList to Array
    // get all values from the input fields
    // remove all empty values
    const addrList = Array.from(nodeList)
        .map(item => item.value)
        .filter(item => item)

    return {
        dgw: vlanForm.querySelector('input#dgw').value,
        dhcp: vlanForm.querySelector('input#dhcp').checked,
        ip: vlanForm.querySelector('input#ip').value,
        iperf: vlanForm.querySelector('input#iperf').checked,
        web: vlanForm.querySelector('input#web').checked,
        isid: vlanForm.querySelector('input#isid').valueAsNumber,
        mcast: {
            client: vlanForm.querySelector('input#mcast-client').value,
            server: vlanForm.querySelector('input#mcast-server').value
        },
        ping: addrList,
        vlanId: vlanForm.querySelector('input#vlanId').valueAsNumber,
    }
}

// ----------------------------------------------------------------------------------------------------
// LLDP
// ----------------------------------------------------------------------------------------------------
const lldpForm = document.querySelector('form#lldp-update-form')

// only show key input if message authentication is enabled
const authCheckBox = lldpForm.querySelector('input#auth')
authCheckBox.addEventListener('change', _ => {
    const keyInput = lldpForm.querySelector('[data-name=key-input]')

    if (authCheckBox.checked) {
        keyInput.classList.remove('hidden')
    } else {
        keyInput.classList.add('hidden')
    }
})

// fill LLDP form with given data
function fillLLDPForm(json) {
    const LLDP_DEVICE_TYPE_MAPPING = {
        'Server': 'Fabric Engine',
        'Proxy': 'Switch Engine',
        'ISW RingV2': 'ISW Switch',
        'Virtual Switch': 'OVS',
        'WLAN Type 1': 'AP',
        'WLAN Type 2': 'AP',
        'Phone': 'Phone',
        'Camera': 'Camera',
    }

    // fill input fields with given values
    lldpForm.querySelector('input#name').value = json.name
    lldpForm.querySelector('input#description').value = json.description
    lldpForm.querySelector('select#Type').value = LLDP_DEVICE_TYPE_MAPPING[json['FA-Element']['Type']]

    lldpForm.querySelector('select#State').value = json['FA-Element'].State
    lldpForm.querySelector('input#MgmtVlan').value = json['FA-Element'].MgmtVlan
    lldpForm.querySelector('select#ProvMode').value = json['FA-Element'].ProvMode

    // if message authentication is enabled show key input field
    lldpForm.querySelector('input#auth').checked = false
    if (json['FA-Element']['msgAuth'] === 'success') {
        lldpForm.querySelector('input#auth').click()
    }

    if (json['FA-Element']['secret']) {
        lldpForm.querySelector('input#key').value = json['FA-Element']['secret']
    }
}

// get input values of the LLDP form and return a dictionary 
function getLLDPForm() {
    const keyEnabled = lldpForm.querySelector('input#auth').checked
    let authKey = lldpForm.querySelector('input#key').value


    const data = {
        'name': lldpForm.querySelector('input#name').value,
        'description': lldpForm.querySelector('input#description').value,
        'FA-Element': {
            'Type': lldpForm.querySelector('select#Type').value,
            'msgAuth': authKey,
            'State': lldpForm.querySelector('select#State').value,
            "MgmtVlan": lldpForm.querySelector('input#MgmtVlan').valueAsNumber,
            "ProvMode": lldpForm.querySelector('select#ProvMode').value,
        },
    }

    if (!keyEnabled) {
        delete data['FA-Element']['msgAuth']
    }

    return data
}