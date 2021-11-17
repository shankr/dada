const mongoose = require('mongoose')

const optionSchema = new mongoose.Schema( {
    name: String
})

const pollSchema = new mongoose.Schema( {
    name: String,
    description: String,
    options: [optionSchema]
})

module.exports = mongoose.model('Poll', pollSchema)