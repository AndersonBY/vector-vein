/**
 * @Author: Bi Ying
 * @Date:   2022-12-01 17:43:11
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-04-30 15:30:40
 */
import { defineStore } from "pinia"


export const useUserRelationalDatabasesStore = defineStore('userRelationalDatabases', {
  state: () => ({
    userRelationalDatabases: JSON.parse(localStorage.getItem("userRelationalDatabases")) || [],
  }),
  actions: {
    setUserRelationalDatabases(userRelationalDatabases) {
      this.userRelationalDatabases = userRelationalDatabases
      localStorage.setItem("userRelationalDatabases", JSON.stringify(this.userRelationalDatabases))
    },
    updateUserRelationalDatabases(userDatabase) {
      this.userRelationalDatabases = this.userRelationalDatabases.map((Database) => {
        if (Database.vid === userDatabase.vid) {
          return userDatabase
        }
        return Database
      })
      localStorage.setItem("userRelationalDatabases", JSON.stringify(this.userRelationalDatabases))
    },
    addUserDatabase(userDatabase) {
      this.userRelationalDatabases.push(userDatabase)
      localStorage.setItem("userRelationalDatabases", JSON.stringify(this.userRelationalDatabases))
    },
    deleteUserDatabase(vid) {
      this.userRelationalDatabases = this.userRelationalDatabases.filter((Database) => Database.vid !== vid)
      localStorage.setItem("userRelationalDatabases", JSON.stringify(this.userRelationalDatabases))
    },
  },
})