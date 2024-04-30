/**
 * @Author: Bi Ying
 * @Date:   2022-12-01 17:43:11
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-29 12:44:28
 */
import { defineStore } from "pinia"
import { formatTime } from "@/utils/util"
import { workflowAPI } from "@/api/workflow"


export const useUserWorkflowsStore = defineStore('userWorkflows', {
  state: () => ({
    userWorkflows: JSON.parse(localStorage.getItem("userWorkflows") || '[]'),
    userWorkflowsTotal: parseInt(localStorage.getItem("userWorkflowsTotal")) || 0,
    userFastAccessWorkflows: JSON.parse(localStorage.getItem("userFastAccessWorkflows") || '[]'),
    diagnosisRecord: null,
    refreshTime: 0,
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
    setDiagnosisRecord(diagnosisRecord) {
      this.diagnosisRecord = diagnosisRecord
    },
    async refreshWorkflows(need_fast_access = true) {
      if (Date.now() - this.refreshTime < 2000) return
      this.refreshTime = Date.now()
      const response = await workflowAPI('list', { need_fast_access: need_fast_access })
      if (response.status == 200) {
        const workflows = response.data.workflows.map(item => {
          item.create_time = formatTime(item.create_time)
          item.update_time = formatTime(item.update_time)
          item.key = item.wid
          return item
        })
        this.setUserWorkflows(workflows)
        const fastAccessWorkflows = response.data.fast_access_workflows.map(item => {
          item.create_time = formatTime(item.create_time)
          item.update_time = formatTime(item.update_time)
          item.key = item.wid
          return item
        })
        this.setUserWorkflows(fastAccessWorkflows, true)
        this.setUserWorkflowsTotal(response.data.total)
      } else {
        console.error(response.msg)
      }
    }
  },
})