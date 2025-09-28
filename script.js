
let currentDate = new Date(); 
let currentYear = currentDate.getFullYear();
let currentMonth = currentDate.getMonth();
let appEvents = [];
let googleEvents = [];
let userID = null;


document.addEventListener('DOMContentLoaded', () => {
    const loginContainer = document.getElementById('login-container');
    const registerContainer = document.getElementById('register-container');
    const mainAppContainer = document.getElementById('main-app-container');
    const showRegisterLink = document.getElementById('show-register');
    const showLoginLink = document.getElementById('show-login');
    const loginForm = document.getElementById('login-form');
    const registerForm = document.getElementById('register-form');
    const addEventForm = document.getElementById('add-event-form');
    const navLinks = document.querySelectorAll('.nav-links a');
    const pages = document.querySelectorAll('.page');
    const logoutLink = document.getElementById('nav-logout');
    const prevMonthBtn = document.getElementById('prev-month-btn');
    const nextMonthBtn = document.getElementById('next-month-btn');
    const googleConnectBtn = document.getElementById('google-connect-btn-in-events');
    const canvasTokenForm = document.getElementById('canvas-token-form');
    const canvasTokenInput = document.getElementById('canvas-token-input');
    const canvasStatus = document.getElementById('canvas-status');

    canvasTokenForm.addEventListener('submit', async e => {
        e.preventDefault();
        const token = canvasTokenInput.value.trim();
        
        if (!token) {
            canvasStatus.textContent = 'Please enter a token.';
            canvasStatus.style.color = 'red';
            return;
        }

        try {
            const response = await fetch('https://horai-dun.vercel.app/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ canvasToken: token })
            })


            const data = await response.json();

            if (response.ok) {
                canvasStatus.textContent = 'Canvas Token Saved Successfully!';
                canvasStatus.style.color = 'green';
                canvasTokenInput.value = ''; 
                loadEventsAndRender();
            } else {
                canvasStatus.textContent = `Error saving token: ${data.error || 'Server error.'}`;
                canvasStatus.style.color = 'red';
            }

        } catch (error) {
            console.error('Canvas connection error:', error);
            canvasStatus.textContent = 'Network error during connection.';
            canvasStatus.style.color = 'red';
        }
    });




    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('loggedin') === 'true') {
        const page = urlParams.get('page');
        showMainApp(page ? `${page}-page` : 'calendar-page');
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    showRegisterLink.addEventListener('click', e => { 
        e.preventDefault(); 
        loginContainer.style.display='none'; 
        registerContainer.style.display='block'; 
    });
    showLoginLink.addEventListener('click', e => { 
        e.preventDefault(); 
        loginContainer.style.display='block'; 
        registerContainer.style.display='none'; 
    });

    loginForm.addEventListener('submit', async e => {
        e.preventDefault();
        const email = loginForm.querySelector('input[type="email"]').value;
        const password = loginForm.querySelector('input[type="password"]').value;
        try {
            const response = await fetch('https://horai-dun.vercel.app/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            if (response.ok) {
                userID = (await response.json()).userID;
                showMainApp();
            } else {
                alert('Login failed. Please check your credentials.');
            }
        } catch (error) {
            console.error('Login error:', error);
            alert('An error occurred during login.');
        }
    });

    registerForm.addEventListener('submit', async e => {
        e.preventDefault();
        const name = registerForm.querySelector('input[type="text"]').value;
        const email = registerForm.querySelector('input[type="email"]').value;
        const password = registerForm.querySelector('input[type="password"]').value;
        try {
            const response = await fetch('https://horai-dun.vercel.app/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });
            if (response.ok) {
                userID = (await response.json()).userID;
                showMainApp();
            } else {
                alert('Registration failed. The email might already be in use.');
            }
        } catch (error) {
            console.error('Registration error:', error);
            alert('An error occurred during registration.');
        }
    });

    if (logoutLink) logoutLink.addEventListener('click', e => { 
        e.preventDefault(); 
        window.location.reload(); 
    });
    
   if (googleConnectBtn) {
        googleConnectBtn.addEventListener('click', () => {
            const codeClient = google.accounts.oauth2.initCodeClient({
                client_id: "768428005792-vqg3ld0gfjlhn10o3e9a5s0avimusjit.apps.googleusercontent.com",
                scope: 'openid email profile https://www.googleapis.com/auth/calendar.readonly',
                ux_mode: 'popup',               
                prompt: 'consent',              
                access_type: 'offline',
                credentials: 'include',
                callback: async (resp) => {
                    const r = await fetch('https://horai-dun.vercel.app/calendarToken', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ userID: userID, code: resp.code })
                    });
                    const data = await r.json();
                    console.log('Auth result:', data);
                },
            });

     codeClient.requestCode();

        });
    }

    function showMainApp(defaultPage = 'calendar-page') {
        loginContainer.style.display = 'none';
        registerContainer.style.display = 'none';
        mainAppContainer.style.display = 'block';
        document.body.classList.add('loggedin');
        showPage(defaultPage);
        loadEventsAndRender();
    }

    function showPage(pageId) {
        pages.forEach(p => p.style.display = p.id === pageId ? 'block' : 'none');
        navLinks.forEach(link => link.classList.toggle('active', link.id === `nav-${pageId.replace('-page', '')}`));
        
    }

    navLinks.forEach(link => {
        if(link.id !== 'nav-logout') {
            link.addEventListener('click', async e => {
                e.preventDefault();
                const pageId = e.target.id.replace('nav-', '') + '-page';
                showPage(pageId);
                
                if (pageId === 'list-page' || pageId === 'calendar-page') { 
                    await loadEventsAndRender(); 
                }
            });
        }
    });

    addEventForm.addEventListener('submit', async e => {
        e.preventDefault();
        
        const title = document.getElementById('event-title').value;
        const type = document.getElementById('event-type').value;
        const dueDateInput = document.getElementById('event-due-date').value;
        const startTimeInput = document.getElementById('event-start-time').value;
        const endTimeInput = document.getElementById('event-end-time').value;
        const priority = document.getElementById('event-priority').value;
        const description = document.getElementById('event-description').value; 
        
        const chatForm = document.getElementById('chat-form');
        const chatInput = document.getElementById('chat-input');
        const chatWindow = document.getElementById('chat-window');

        let payload = {
            title, 
            type, 
            description,
            priority,
            dueDate: null,
            startTime: null,
            endTime: null
        };

        if (startTimeInput && endTimeInput) {
            payload.startTime = startTimeInput;
            payload.endTime = endTimeInput;
        } else if (dueDateInput) {
            payload.dueDate = dueDateInput;
        }
        
        try {
            const response = await fetch('http://localhost:3000/api/events', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload) 
            });
            
            if(response.ok){
                const newEvent = await response.json();
                appEvents.push(newEvent);
                addEventForm.reset();
                alert(`Successfully created task: ${newEvent.title}`); 
                showPage('list-page');
                loadEventsAndRender();
            } else {
                try {
                    const errorData = await response.json();
                    alert(`Failed to create event: ${errorData.error || response.statusText}`);
                } catch (e) {
                    alert(`Failed to create event. Server returned status: ${response.status}`);
                }
            }
        } catch (error) {
            console.error('Network or Fetch error:', error);
            alert('A network error occurred. Ensure your backend server is running on port 3000.');
        }
    });

    chatForm.addEventListener('submit', async e => {
        e.preventDefault();
        const userInput = chatInput.value.trim();
        if (!userInput) return;

        addMessageToChat(userInput, 'user');
        chatInput.value = '';

        try {
            const response = await fetch('https://horai-dun.vercel.app/api/chatbot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: userInput })
            });

            if (response.ok) {
                const data = await response.json();
                addMessageToChat(data.response, 'bot');
            } else {
                addMessageToChat('Error: Could not connect to the scheduling engine.', 'bot');
            }
        } catch (error) {
            console.error('Chatbot fetch error:', error);
            addMessageToChat('Network error. Check your server connection.', 'bot');
        }
    });


    async function loadEventsAndRender() {
    let allEvents = [];

    try {
        const res = await fetch('https://horai-dun.vercel.app/api/events'); 
        
        if(res.ok) {
            allEvents = await res.json();
        } else {
            console.error("Failed to fetch unified schedule. Status:", res.status);
        }
    } catch(e){ 
        console.error("Network error fetching events:", e);
    }

    renderCalendar(currentYear, currentMonth, allEvents);
    renderTodoList(allEvents);
    }


    function renderCalendar(year, month, events = []) {
        const calendarGrid = document.getElementById('calendar-grid'); 
        const weekdaysContainer = document.getElementById('calendar-weekdays');

        calendarGrid.innerHTML = '';
        weekdaysContainer.innerHTML = '';
        
        const dayNames = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
        const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        
        let startDate = new Date(currentDate);
        let endDate = new Date(startDate);
        endDate.setDate(startDate.getDate() + 6);

        const startMonthName = monthNames[startDate.getMonth()];
        const endMonthName = monthNames[endDate.getMonth()];
        
        let headerText = `${startMonthName} ${startDate.getDate()}`;
        if (startDate.getMonth() !== endDate.getMonth() || startDate.getFullYear() !== endDate.getFullYear()) {
            headerText += ` - ${endMonthName} ${endDate.getDate()}, ${endDate.getFullYear()}`;
        } else {
            headerText += ` - ${endDate.getDate()}, ${endDate.getFullYear()}`;
        }
        document.getElementById('month-year-header').textContent = headerText;

        weekdaysContainer.innerHTML = '<div></div>'; 
        for (let i = 0; i < 7; i++) {
            let dayToDisplay = new Date(startDate);
            dayToDisplay.setDate(startDate.getDate() + i);
            
            const dayDiv = document.createElement('div');
            dayDiv.innerHTML = `${dayNames[dayToDisplay.getDay()]} ${dayToDisplay.getDate()}`; 
            weekdaysContainer.appendChild(dayDiv);
        }
        
        for (let hour = 0; hour < 24; hour++) {
            const hourLabel = hour === 0 ? '12 AM' : hour < 12 ? `${hour} AM` : hour === 12 ? '12 PM' : `${hour - 12} PM`;
            
            const timeCell = document.createElement('div');
                timeCell.classList.add('time-axis-cell');
                timeCell.textContent = hourLabel;
                calendarGrid.appendChild(timeCell);

                for (let i = 0; i < 7; i++) {
                    let dayToRender = new Date(startDate);
                    dayToRender.setDate(startDate.getDate() + i);

                    const dayCell = document.createElement('div');
                    dayCell.classList.add('schedule-day-cell');
                    dayCell.dataset.date = dayToRender.toDateString(); 
                    dayCell.dataset.hour = hour;
                    
                    calendarGrid.appendChild(dayCell);
                }
            }
            
            events.forEach(evt => {
                const standardStartTime = evt['start time'] || evt.startTime;
                const standardEndTime = evt.endtime || evt.endTime;
                const standardDueDate = evt.duedate || evt.dueDate; 
                const standardTitle = evt.title;
                const standardPriority = evt.priority; 
                const eventId = evt.id; 
                
                const hasStartEnd = !!standardStartTime && !!standardEndTime;
                
                const eventDateStr = standardStartTime || standardDueDate; 
                
                if (!eventDateStr) return;

                const eventStart = new Date(eventDateStr);
                let eventEnd = new Date(standardEndTime || eventDateStr);
                
                if (standardDueDate && !hasStartEnd) {
                    eventStart.setHours(9, 0, 0); 
                    eventEnd.setTime(eventStart.getTime() + 60 * 60 * 1000);
                }
                
                const eventDay = eventStart.toDateString();
                const startHour = eventStart.getHours();
                const startMinute = eventStart.getMinutes();
                
                const durationMinutes = (eventEnd.getTime() - eventStart.getTime()) / 60000;
                const renderDuration = Math.max(durationMinutes, durationMinutes > 0 ? 0 : 30);
                
                const topPercent = (startMinute / 60) * 100;
                const heightPercent = (renderDuration / 60) * 100;

                const targetCell = calendarGrid.querySelector(`.schedule-day-cell[data-date="${eventDay}"][data-hour="${startHour}"]`);

                if (targetCell) {
                    const eventDiv = document.createElement('div');
                    eventDiv.classList.add('schedule-event');
                    
                    eventDiv.dataset.eventId = eventId;
                    
                    eventDiv.textContent = standardTitle || 'Untitled Event';
                    eventDiv.style.top = `${topPercent}%`;
                    eventDiv.style.height = `${heightPercent}%`;

                    targetCell.appendChild(eventDiv);
                }
            });
    }


    function renderTodoList(events = []) {
        const todoListContainer = document.getElementById('todo-list-container');
        if (!todoListContainer) return;


        todoListContainer.innerHTML = ''; 

        if (events.length === 0) {
            todoListContainer.innerHTML = '<p class="empty-list-message">You have no tasks or events scheduled. Time to get organized! 🎉</p>';
            return;
        }

        const ul = document.createElement('ul');
        ul.classList.add('todo-list');

        events.forEach(event => {
            const li = document.createElement('li');
            li.classList.add('todo-item');

            const title = event.title || event.summary;
            const type = event.type || 'Task';
            
            const dateStr = event.startTime || event.duedate || event.start?.dateTime || event.start?.date; 
            
            const eventDate = dateStr ? new Date(dateStr) : null;
            
            const formattedDate = eventDate ? 
                eventDate.toLocaleDateString() + (event.startTime || event.start?.dateTime ? ' ' + eventDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '') : 
                'No Date';

            li.classList.add(event.type ? event.type.toLowerCase() : 'task'); 

            li.innerHTML = `
                <div class="todo-details">
                    <span class="todo-title">${title}</span>
                    <span class="todo-meta">
                        <span class="todo-type">Type: ${type}</span>
                        |
                        <span class="todo-date">Due: ${formattedDate}</span>
                    </span>
                </div>
            `;
            ul.appendChild(li);
        });

        todoListContainer.appendChild(ul);
    }


    if (prevMonthBtn) {
        prevMonthBtn.addEventListener('click', () => {
            currentDate.setDate(currentDate.getDate() - 7);
            loadEventsAndRender();
        });
    }
    if (nextMonthBtn) {
        nextMonthBtn.addEventListener('click', () => {
            currentDate.setDate(currentDate.getDate() + 7);
            loadEventsAndRender();
        });
    }
});
function addMessageToChat(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('chat-message', `${sender}-message`);
        messageDiv.textContent = text;
        chatWindow.appendChild(messageDiv);
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }


