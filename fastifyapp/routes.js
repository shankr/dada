const pollController = require("./controllers/pollcontroller")
const pollResponseSchema = {
    '_id': { type: 'string'},
    'name': { type: 'string'},
    'options': { 
        type: 'array',
        items: {
            'name': { type: 'string'},
            '_id': { type: 'string' }
        }
    }
}
const createPollSchema = {
    'body': {
        'name': { type: 'string'},
        'description': { type: 'string'},
        'options': { 
            type: 'array',
            items: {
                'name': { type: 'string'},
                '_id': { type: 'string' }
            }
        }
    },
    'response': {
        '200': pollResponseSchema
    }
}

const routes = [
    {
        method: 'GET',
        url: '/polls',
        handler: pollController.getPolls,
        schema: pollResponseSchema
    },

    {
        method: 'GET',
        url: '/polls/:id',
        handler: pollController.getPoll
    },

    {
        method: 'POST',
        url: '/polls',
        schema: createPollSchema,
        handler: pollController.createPoll
    },

    {
        method: 'PUT',
        url: '/polls/:id',
        handler: pollController.updatePoll
    },

    {
        method: 'DELETE',
        url: '/polls/:id',
        handler: pollController.deletePoll
    },

    {
        method: 'GET',
        url: '/',
        handler: async (req, resp) => {
            resp.sendFile('index.html')
        }
    }
]

module.exports = routes

/*
const {createPoll, getPolls, getPoll, updatePoll} = require("./controllers/pollcontroller")

function itemRoutes(fastify, options, done) {
    fastify.get("/", (req, resp) => {
        resp.sendFile('index.html')
    })

    fastify.post("/polls", (req, resp) => {
        const poll = createPoll(req, resp)
        resp.send(poll)
    })

    fastify.get("/polls", async (req, resp) => {
        const polls = await getPolls(req, resp)
        resp.send(polls)
    })

    fastify.get("/polls/:id", async (req, resp) => {
        const poll = await getPoll(req, resp)
        resp.send(poll)
    })


    fastify.put("/polls/:id", async (req, resp) => {
        const poll = await updatePoll(req, resp)
        resp.send(poll)
    })
*/

/*
    let items = require('./Items')
    const {v4: uuidv4} = require('uuid')

    fastify.get("/items", (req, resp) => {
        resp.send(items)
    })
    
    fastify.get("/items/:id", (req, resp) => {
        const {id} = req.params
        const item = items.find((item) => item.id == id)
        resp.send(item)
    })
    
    fastify.post("/items", (req, resp) => {
        const {name} = req.body
        const item = {
            id: uuidv4(),
            name
        }
        items = [...items, item]
        resp.send(item)
    })

    fastify.delete("/items/:id", (req, resp) => {
        const {id} = req.params
        const item = items.find(item => item.id == id)
        items = items.filter(item => item.id != id)
        resp.send(item)
    })

    fastify.put("/items/:id", (req, resp) => {
        const {id} = req.params
        const {name} = req.body
        const item = items.find(item => item.id == id)
        item.name = name
        resp.send(item)
    })

    done()
}

module.exports=itemRoutes
*/

