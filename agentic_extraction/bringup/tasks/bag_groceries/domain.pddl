(define (domain domain_pddl)
    (:requirements :negative-preconditions :typing)
      (:types
    locatable location - object
    robot item furniture - locatable
    container food - item
    sack - container
    checkout - furniture
    canned_food egg apple - food
    bottle_of_orange_juice - item
  )
  (:predicates
    (at ?e - locatable ?l - location)
    (in ?o - item ?c - container)
    (on_top ?top - item ?bottom - locatable)
    (holding ?r - robot ?o - item)
    (robot_free ?r - robot)
    (open ?c - container)
  )

  (:action drive
    :parameters (?r - robot ?from - location ?to - location)
    :precondition (at ?r ?from)
    :effect (and (not (at ?r ?from)) (at ?r ?to))
  )

  (:action pick
    :parameters (?r - robot ?o - item ?l - location)
    :precondition (and (at ?r ?l) (at ?o ?l) (robot_free ?r))
    :effect (and (holding ?r ?o) (not (at ?o ?l)) (not (robot_free ?r)))
  )

  (:action open
    :parameters (?r - robot ?c - container ?l - location)
    :precondition (and (at ?r ?l) (at ?c ?l) (robot_free ?r) (not (open ?c)))
    :effect (open ?c)
  )

  (:action place_in_container
    :parameters (?r - robot ?o - item ?c - container ?l - location)
    :precondition (and (at ?r ?l) (at ?c ?l) (holding ?r ?o) (open ?c))
    :effect (and (in ?o ?c) (robot_free ?r) (not (holding ?r ?o)))
  )
)
