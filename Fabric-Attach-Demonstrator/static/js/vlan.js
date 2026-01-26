// dictionary that maps incoming state to css classes
const stateMap = {
    0: 'bg-yellow-100', // pending / unknown
    1: 'bg-green-200',  // on
    2: 'bg-red-200'     // off
}

// table body of the VLAN table
const tbody = document.querySelector('tbody[data-name=table-body]')

// remove all present VLANs in the table
function clearTable() {
    tbody.innerHTML = ''
}

// add new VLAN to the table
function displayVLAN(vlan) {
    // get the corresponding row in the table (is 'null' if not present)
    const oldRow = tbody.querySelector(`tr[data-vlan-id='${vlan.vlanId}']`)

    // create new row
    const newRow = createRowFromVLAN(vlan)

    // replace old row if it exists
    // otherwise append the new row to the table
    if (oldRow === null) {
        tbody.appendChild(newRow)
    } else {
        oldRow.replaceWith(newRow)
    }
}

// populate row element with incoming data
function createRowFromVLAN(vlan) {
    // get row element from template
    const template = document.querySelector('template#table-row')
    const row = template.content.cloneNode(true).firstElementChild
    row.setAttribute('data-vlan-id', vlan.vlanId)

    // fill row with data for every key that does not need extra processing
    const keys = ['dgw', 'ip', 'vlanId', 'isid']
    for (const key of keys) {
        const element = row.querySelector(`[data-name=${key}]`)
        element.textContent = vlan[key]
    }

    // add ping addresses
    for (const addr of vlan.ping) {
        // skip empty address (i.e. string is empty)
        if (addr) {
            // get cell in row and add span element
            const element = row.querySelector(`[data-name=ping]`)
            const span = document.createElement('span')

            // set address as element-attribute (to add status later)
            span.setAttribute('addr', addr)

            // fill span with text
            span.textContent = addr

            // add span to cell
            element.appendChild(span)
        }
    }

    // check if dhcp/iperf key is present in the vlan dict
    // convert the boolean to 0 / 1
    // show the corresponding icon in the row-cell
    for (const key of ['dhcp', 'iperf', 'web']) {
        const disabled = Number(!vlan[key])
        row.querySelector(`[data-name=${key}]`).children[disabled].classList.remove('hidden')
    }

    // fill row with MCAST data
    for (const key of ['server', 'client']) {
        const cell = row.querySelector(`[data-name=mcast-${key}]`)
        cell.textContent = vlan['mcast'][key]
    }

    const optionsCell = row.querySelector('[data-name=options]')

    // add event listener for the edit button
    const editBtn = optionsCell.querySelector('[data-name=edit]')
    editBtn.addEventListener('click', _ => {
        // set form method to PATCH
        vlanForm.setAttribute('data-method', 'PATCH')

        // fill VLAN form
        fillVLANForm(vlan)

        // show dialog
        vlanModal.show()
    })

    // add event listener for the delete button
    const deleteBtn = optionsCell.querySelector('[data-name=delete]')
    deleteBtn.addEventListener('click', _ => {
        // set VLAN id in modal message
        deleteModalElement.querySelector('b#vlanId-confirm').textContent = vlan.vlanId + ':' + vlan.isid

        // get modal delete confirm button and set event handler
        const deleteBtn = deleteModalElement.querySelector('button[data-vlan-id]')
        deleteBtn.setAttribute('data-vlan-id', vlan.vlanId)

        // show modal
        deleteModal.show()
    })

    return row
}

function setVLANState(id, state) {
    // get table row with corresponding VLAN id
    const row = tbody.querySelector(`tr[data-vlan-id="${id}"]`)

    // ignore VLAN states if there is no config
    if (row === null) {
        console.debug(`config for id ${id} could not be found!`)
        return
    }

    // clear all previous states
    clearState(row)

    // add styles to table cells according to the state data
    row.querySelector('[data-name=dgw]').classList.add(stateMap[state.dgw])
    row.querySelector('[data-name=ip]').classList.add(stateMap[state.ip])
    row.querySelector('[data-name=isid]').classList.add(stateMap[state.isid])
    row.querySelector('[data-name=vlanId]').classList.add(stateMap[state.vlanId])

    row.querySelector('[data-name=mcast-client]').classList.add(stateMap[state.mcast.client])
    row.querySelector('[data-name=mcast-server]').classList.add(stateMap[state.mcast.server])

    // get all ping addresses in row
    const addrList = row.querySelector('[data-name=ping]').querySelectorAll('span')
    for (const item of addrList) {
        // add style to each address
        const addr = item.getAttribute('addr')
        item.classList.add(stateMap[state.ping[addr]])
    }
}

function clearState(element) {
    // remove all classes from the selected elements
    element.querySelector('[data-name=dgw]').removeAttribute('class')
    element.querySelector('[data-name=ip]').removeAttribute('class')
    element.querySelector('[data-name=isid]').removeAttribute('class')
    element.querySelector('[data-name=vlanId]').removeAttribute('class')

    element.querySelector('[data-name=mcast-client]').removeAttribute('class')
    element.querySelector('[data-name=mcast-server]').removeAttribute('class')

    // remove all classes from each address
    const addrList = element.querySelector('[data-name=ping]').querySelectorAll('span')
    addrList.forEach(item => item.removeAttribute('class'))
}
