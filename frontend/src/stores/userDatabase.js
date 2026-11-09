/**
 * @Author: Bi Ying
 * @Date:   2022-12-01 17:43:11
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2023-04-30 15:30:40
 */
import { defineStore } from "pinia"


export const useUserDatabasesStore = defineStore('userDatabases', {
  state: () => ({
    userDatabases: [],
  }),
  actions: {
    setUserDatabases(userDatabases) {
      this.userDatabases = userDatabases || []
    },
    updateUserDatabases(userDatabase) {
      this.userDatabases = this.userDatabases.map((Database) => {
        if (Database.id === userDatabase.id) {
          return userDatabase
        }
        return Database
      })
    },
    addUserDatabase(userDatabase) {
      this.userDatabases.push(userDatabase)
    },
    deleteUserDatabase(vid) {
      this.userDatabases = this.userDatabases.filter((Database) => Database.id !== vid)
    },
  },
})