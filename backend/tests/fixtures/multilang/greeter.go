// Fixture: Go module.
package main

import "fmt"

// Greet writes a greeting.
func Greet(name string) string {
	return fmt.Sprintf("hello %s", name)
}

type Greeter struct {
	Prefix string
}

// Greet is the method form.
func (g Greeter) Greet(name string) string {
	return g.Prefix + " " + name
}
