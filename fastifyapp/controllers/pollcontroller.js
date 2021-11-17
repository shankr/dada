let Poll = require("../models/poll");

const getPolls = async (req, resp) => {
    try {
        const polls = await Poll.find()
        return polls
    } catch (error) {
        console.log(error)
    }
}

const getPoll = async (req, resp) => {
    const {id} = req.params
    try {
        const poll = await Poll.findById(id)
        return poll
    } catch (error) {
        console.log(error)
    }
}

const createPoll = (req, resp) => {
    try {
        poll = new Poll(req.body)
        poll.save()
        return poll
    } catch (error) {
        console.log(error)
    }
}

const updatePoll = async (req, resp) => {
    try {
        const {id} = req.params;
        const {...updateData} = req.body
        const update = await Poll.findByIdAndUpdate(id, updateData, {new: true})
        return update
    } catch (error) {
        console.log(error)
    }
}

const deletePoll = async (req, resp) => {
    try {
        const {id} = req.params;
        const poll = await Poll.findByIdAndDelete(id)
        return poll
    } catch (error) {
        console.log(error)
    }
}

module.exports = {createPoll, getPolls, getPoll, updatePoll, deletePoll}
