import { Admin, User } from "./user";

const moduleUser: User = new User();
moduleUser.save();

export function work(): string {
  const typed: User = new User();
  const constructed = new User();
  return typed.load() + constructed.save();
}

export function adminWork(): string {
  const typed: Admin = new Admin();
  return typed.save();
}

export function parameterWork(user: User): string {
  return user.load();
}

class Controller {
  private user = new User();

  help(): string {
    return "help";
  }

  persist(): string {
    // Chained receiver: must not resolve to Controller.help/save.
    return this.user.save();
  }

  local(): string {
    return this.help();
  }

  save(): string {
    return "controller-saved";
  }
}
