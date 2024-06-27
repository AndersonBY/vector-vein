/**
 * @Author: Bi Ying
 * @Date:   2023-12-11 18:08:13
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-12-17 20:41:13
 */
import { defineStore } from "pinia"


export const useUserAgentsStore = defineStore('userAgents', {
  state: () => ({
    agents: [],
    agentsLength: 0,
  }),
  actions: {
    getAgent(aid) {
      return this.agents.find(agent => agent.aid === aid)
    },
    addAgent(agent) {
      const index = this.agents.findIndex(c => c.aid === agent.aid)
      if (index !== -1) {
        return
      }
      this.agents.push(agent)
      this.agentsLength = this.agents.length
    },
    deleteAgent(aid) {
      this.agents = this.agents.filter(agent => agent.aid !== aid)
      this.agentsLength = this.agents.length
    },
    updateAgent(aid, key, value) {
      const index = this.agents.findIndex(agent => agent.aid === aid)
      this.agents[index][key] = value
    }
  },
})