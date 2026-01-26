const state = {
    'success': {
        container: ['text-green-800', 'bg-green-50', 'border-green-300', 'dark:bg-gray-800', 'dark:text-green-400', 'dark:border-green-800'],
        button: ['bg-green-50', 'text-green-500', 'focus:ring-green-400', 'hover:bg-green-200', 'dark:bg-gray-800', 'dark:text-green-400', 'dark:hover:bg-gray-700']
    },
    'error': {
        container: ['text-red-800', 'bg-red-50', 'border-red-300', 'dark:bg-gray-800', 'dark:text-red-400', 'dark:border-red-800'],
        button: ['bg-red-50', 'text-red-500', 'focus:ring-red-400', 'hover:bg-red-200', 'dark:bg-gray-800', 'dark:text-red-400', 'dark:hover:bg-gray-700']
    }
}

// creates an notification and adds the new HTML element to the page
function createToast(message, type, timeout) {
    // get HTML template
    const template = document.querySelector('template#toast')
    const toast = template.content.cloneNode(true).firstElementChild

    // set css classes
    const toastState = state[type]
    toast.classList.add(...toastState.container)
    toast.querySelector('button').classList.add(...toastState.button)

    // set message and add onclick callback for the close button
    toast.querySelector('[data-name=toast-message]').textContent = message
    const closeBtn = toast.querySelector('button[data-name=toast-close]')
    closeBtn.addEventListener('click', _ => {
        toast.remove()
    })

    // add notification to page
    const wrapper = document.querySelector('#toast-wrapper')
    wrapper.appendChild(toast)

    // remove notification after timeout
    setTimeout(() => {
        toast.remove()
    }, timeout)
}