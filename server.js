require('dotenv').config()
const express = require('express')
const path = require('path')
const mongoose = require('mongoose')
const { google } = require('googleapis')
const session = require('express-session')
const bcrypt = require('bcrypt')

const app = express()
const port = process.env.PORT || 3000

mongoose.connect(process.env.MONGO_URI, { useNewUrlParser: true, useUnifiedTopology: true })

app.use(express.json())
app.use(express.static(__dirname))
app.use(session({ secret: 'horai-secret', resave: false, saveUninitialized: true }))

const oauth2Client = new google.auth.OAuth2(
    process.env.GOOGLE_CLIENT_ID,
    process.env.GOOGLE_CLIENT_SECRET,
    `http://localhost:${port}/oauth2callback`
)
const scopes = [
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/calendar.events'
]

const userSchema = new mongoose.Schema({
    name: String,
    email: String,
    password: String,
    googleTokens: Object,
    canvasToken: String
})
const User = mongoose.model('User', userSchema)

const eventSchema = new mongoose.Schema({
    userId: mongoose.Schema.Types.ObjectId,
    title: String,
    type: String,
    dueDate: Date,
    description: String
})
const Event = mongoose.model('Event', eventSchema)

app.get('/', (req, res) => res.sendFile(path.join(__dirname, 'index.html')))

app.post('/api/register', async (req, res) => {
    const { name, email, password } = req.body
    const existing = await User.findOne({ email })
    if (existing) return res.status(400).json({ error: 'Email already used' })
    const hash = await bcrypt.hash(password, 10)
    const user = await User.create({ name, email, password: hash })
    req.session.userId = user._id
    res.json({ success: true })
})

app.post('/api/login', async (req, res) => {
    const { email, password } = req.body
    const user = await User.findOne({ email })
    if (!user) return res.status(400).json({ error: 'Invalid credentials' })
    const ok = await bcrypt.compare(password, user.password)
    if (!ok) return res.status(400).json({ error: 'Invalid credentials' })
    req.session.userId = user._id
    res.json({ success: true })
})

app.post('/api/logout', (req, res) => {
    req.session.destroy(() => res.json({ success: true }))
})

app.get('/api/events', async (req, res) => {
    if (!req.session.userId) return res.status(401).json({ error: 'Not logged in' })
    
    const testSchedule = [
        {
            "id": "flex-task-1",
            "title": "Study Math",
            "desc": "Study Math",
            "priority": "High", // Added priority for complete testing
            "startTime": "2025-09-29T10:30:00Z", 
            "endTime": "2025-09-29T12:30:00Z",
            "dueDate": null
        }
    ];
    
    res.json(testSchedule);

    //const events = await Event.find({ userId: req.session.userId })
    //res.json(events)


})


app.post('/api/events', async (req, res) => {
    if (!req.session.userId) return res.status(401).json({ error: 'Not logged in' });
    
    const { title, type, dueDate, description, startTime, endTime, priority } = req.body;

    const hasDueDate = !!dueDate;
    const hasStartAndEndTime = !!startTime && !!endTime;

    if (!hasDueDate && !hasStartAndEndTime) {
        return res.status(400).json({ 
            error: 'Event must have either a Due Date, OR both a Start Time and End Time.' 
        });
    }

    if (hasStartAndEndTime && new Date(startTime) >= new Date(endTime)) {
        return res.status(400).json({
            error: 'Start Time must be before End Time.'
        });
    }

    try {
        const evt = await Event.create({ 
            userId: req.session.userId, 
            title, 
            type, 
            dueDate, 
            description,
            startTime, 
            endTime,   
            priority   
        });
        
        res.json(evt);
    } catch (err) {
        console.error("Database error creating event:", err);
        res.status(500).json({ error: 'Failed to save event to database.' });
    }
});

app.get('/api/google-auth', (req, res) => {
    const url = oauth2Client.generateAuthUrl({ access_type: 'offline', scope: scopes })
    res.redirect(url)
})

app.get('/oauth2callback', async (req, res) => {
    if (!req.session.userId) {
        return res.status(401).send('Please log in before connecting your Google Calendar.')
    }
    const code = req.query.code
    try {
        const { tokens } = await oauth2Client.getToken(code)
        
        await User.findByIdAndUpdate(
            req.session.userId, 
            { googleTokens: tokens }
        )

        req.session.googleTokens = tokens 

        res.redirect('/?loggedin=true&page=add-event')
    } catch (err) {
        console.error('Google token exchange failed:', err.message)
        res.status(500).send('Google authentication failed.')
    }
})

app.get('/api/google-events', async (req, res) => {
    if (!req.session.userId) return res.status(401).json({ error: 'Not logged in' })
    
    const user = await User.findById(req.session.userId)
    if (!user || !user.googleTokens) {
        return res.status(401).json({ error: 'Google Calendar not connected' })
    }

    oauth2Client.setCredentials(user.googleTokens)

    if (oauth2Client.isTokenExpiring() && user.googleTokens.refresh_token) {
        try {
            const { credentials } = await oauth2Client.refreshAccessToken()
            
            await User.findByIdAndUpdate(
                req.session.userId, 
                { googleTokens: credentials }
            )
            req.session.googleTokens = credentials
        } catch (err) {
            console.error('Failed to refresh access token:', err.message)
            await User.findByIdAndUpdate(req.session.userId, { googleTokens: null })
            return res.status(401).json({ error: 'Google token expired, please reconnect.' })
        }
    }

    try {
        const calendar = google.calendar({ version: 'v3', auth: oauth2Client })
        const now = new Date()
        const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1)
        const endOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0)
        
        const response = await calendar.events.list({ 
            calendarId: 'primary',
            timeMin: startOfMonth.toISOString(), 
            timeMax: endOfMonth.toISOString(), 
            singleEvents: true,
            orderBy: 'startTime'
        })
        
        const events = response.data.items.map(evt => ({
            id: evt.id,
            summary: evt.summary,
            start: evt.start,
            end: evt.end
        }))
        res.json(events)
    } catch (err) {
        console.error('Error fetching Google events:', err.message)
        res.status(500).json({ error: 'Could not fetch Google events.' })
    }
})

app.post('/api/connect-canvas', async (req, res) => {
    if (!req.session.userId) {
        return res.status(401).json({ error: 'Not logged in' });
    }

    const { canvasToken } = req.body;
    const tokenToSave = canvasToken || null; 

    try {
        const updatedUser = await User.findByIdAndUpdate(
            req.session.userId,
            { canvasToken: tokenToSave },
            { new: true }
        );

        res.json({ 
            success: true, 
            message: updatedUser.canvasToken ? 'Canvas token saved.' : 'Canvas token cleared.',
            userId: updatedUser._id,
            canvasToken: updatedUser.canvasToken
        });
    } catch (err) {
        console.error('Error saving Canvas token:', err);
        res.status(500).json({ error: 'Failed to save token to database.' });
    }
});

app.post('/api/chatbot', async (req, res) => {
    if (!req.session.userId) {
        return res.status(401).json({ error: 'Not logged in' });
    }
    
    const { prompt } = req.body;

    if (!prompt) {
        return res.status(400).json({ error: 'Prompt is required.' });
    }

    try {
       
        await new Promise(resolve => setTimeout(resolve, 1500));
        const modelResponse = {
            responseText: `I received your request: "${prompt}". Processing the optimal schedule now. Please check your calendar shortly!`
        };


        res.json({ response: modelResponse.responseText });

    } catch (err) {
        console.error('External Model Error:', err);
        res.status(500).json({ error: 'Failed to communicate with the scheduling model.' });
    }
});

app.listen(port, () => console.log(`Server running at http://localhost:${port}`))