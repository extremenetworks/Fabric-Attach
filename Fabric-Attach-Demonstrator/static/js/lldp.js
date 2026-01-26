const msgAuthMap = {
    'success': 'bg-green-200',
    'disabled': 'bg-yellow-100',
    'failed': 'bg-red-200'
}

function createLLDPTable(element, json, type) {
    const keys = ['name', 'description', 'capabilities', 'ip', 'port']
    for (const key of keys) {
        element.querySelector(`[data-name=${key}]`).textContent = json[key]
    }

    // fill in content of "FA-Element"
    const FAKeys = ['System-ID', 'Type', 'msgAuth', 'MgmtVlan', 'ProvMode', 'State']
    const FAElement = json["FA-Element"]
    for (const key of FAKeys) {
        element.querySelector(`[data-name=${key}]`).textContent = FAElement[key]

        if (key === 'msgAuth' && type === 'inbound') {
            const state = FAElement[key]
            if (state in msgAuthMap) {
                element.querySelector(`[data-name=${key}]`).removeAttribute('class')
                element.querySelector(`[data-name=${key}]`).classList.add(msgAuthMap[state])
            }
        }
    }

    // add event listener for config change
    if (type === 'outbound') {
        const editLLDPButton = element.querySelector('button[data-name=edit-lldp]')
        editLLDPButton.addEventListener('click', _ => {
            fillLLDPForm(json)
            lldpModal.show()
        })
    }
}