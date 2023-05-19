/**
 * @Author: Bi Ying
 * @Date:   2022-12-01 17:43:11
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-04-30 15:30:40
 */
import { defineStore } from "pinia"


export const useUserDatabasesStore = defineStore('userDatabases', {
  state: () => ({
    userDatabases: JSON.parse(localStorage.getItem("userDatabases")) || [],
  }),
  actions: {
    setUserDatabases(userDatabases) {
      this.userDatabases = userDatabases
      localStorage.setItem("userDatabases", JSON.stringify(this.userDatabases))
    },
    updateUserDatabases(userDatabase) {
      this.userDatabases = this.userDatabases.map((Database) => {
        if (Database.vid === userDatabase.vid) {
          return userDatabase
        }
        return Database
      })
      localStorage.setItem("userDatabases", JSON.stringify(this.userDatabases))
    },
    addUserDatabase(userDatabase) {
      this.userDatabases.push(userDatabase)
      localStorage.setItem("userDatabases", JSON.stringify(this.userDatabases))
    },
    deleteUserDatabase(vid) {
      this.userDatabases = this.userDatabases.filter((Database) => Database.vid !== vid)
      localStorage.setItem("userDatabases", JSON.stringify(this.userDatabases))
    },
  },
})