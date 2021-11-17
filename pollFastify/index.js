const fastify = require('fastify') ({logger: true})
const routes = require('./routes')
const path = require('path')
fastify.register(require('fastify-formbody'))

fastify.register(require('fastify-static'), {
    root: path.join(__dirname, 'public'),
    prefix: '/public/', // optional: default '/'
  })
  
const mongoose = require("mongoose")
mongoose.connect('mongodb://localhost/users')
        .then(() => console.log('MongoDB connected…'))
        .catch(err => console.log(err))
routes.forEach((route, index) => {
    fastify.route(route)
})

const start = async() => {
    try {
        await fastify.listen(5000)
    } catch (error) {
        fastify.log.error(error)
        process.exit(1)
    }
}

start()