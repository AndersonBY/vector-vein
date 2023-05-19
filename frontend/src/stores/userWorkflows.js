/**
 * @Author: Bi Ying
 * @Date:   2022-12-01 17:43:11
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-05-10 21:54:15
 */
import { defineStore } from "pinia"


export const useUserWorkflowsStore = defineStore('userWorkflows', {
  state: () => ({
    userWorkflows: localStorage.getItem("userWorkflows") || [],
    userWorkflowsTotal: localStorage.getItem("userWorkflowsTotal") || 0,
    userFastAccessWorkflows: localStorage.getItem("userFastAccessWorkflows") || [],
  }),
  actions: {
    setUserWorkflowsTotal(userWorkflowsTotal) {
      this.userWorkflowsTotal = userWorkflowsTotal
      localStorage.setItem("userWorkflowsTotal", this.userWorkflowsTotal)
    },
    setUserWorkflows(userWorkflows, isFastAccess = false) {
      if (isFastAccess) {
        this.userFastAccessWorkflows = userWorkflows
        localStorage.setItem("userFastAccessWorkflows", JSON.stringify(this.userFastAccessWorkflows))
      } else {
        this.userWorkflows = userWorkflows
        localStorage.setItem("userWorkflows", JSON.stringify(this.userWorkflows))
      }
    },
    updateUserWorkflow(userWorkflow, isFastAccess = false) {
      if (isFastAccess) {
        this.userFastAccessWorkflows = this.userFastAccessWorkflows.map((workflow) => {
          if (workflow.wid === userWorkflow.wid) {
            return userWorkflow
          }
          return workflow
        })
        localStorage.setItem("userFastAccessWorkflows", JSON.stringify(this.userFastAccessWorkflows))
      } else {
        this.userWorkflows = this.userWorkflows.map((workflow) => {
          if (workflow.wid === userWorkflow.wid) {
            return userWorkflow
          }
          return workflow
        })
        localStorage.setItem("userWorkflows", JSON.stringify(this.userWorkflows))
      }
    },
    addUserWorkflow(userWorkflow, isFastAccess = false) {
      if (isFastAccess) {
        this.userFastAccessWorkflows.unshift(userWorkflow)
        localStorage.setItem("userFastAccessWorkflows", JSON.stringify(this.userFastAccessWorkflows))
      } else {
        this.userWorkflows.unshift(userWorkflow)
        localStorage.setItem("userWorkflows", JSON.stringify(this.userWorkflows))
      }
    },
    deleteUserWorkflow(wid, isFastAccess = false) {
      if (isFastAccess) {
        this.userFastAccessWorkflows = this.userFastAccessWorkflows.filter((workflow) => workflow.wid !== wid)
        localStorage.setItem("userFastAccessWorkflows", JSON.stringify(this.userFastAccessWorkflows))
      } else {
        this.userWorkflows = this.userWorkflows.filter((workflow) => workflow.wid !== wid)
        localStorage.setItem("userWorkflows", JSON.stringify(this.userWorkflows))
      }
    },
  },
})