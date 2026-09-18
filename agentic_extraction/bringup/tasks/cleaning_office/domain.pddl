(define (domain domain_pddl)
    (:requirements :negative-preconditions :typing)
    (:types
    locatable location - object
    robot item furniture - locatable
    container device food - item
    computer keyboard mouse - device
    carton recycling_bin - container
    desk floor - furniture
    legal_document sheet pen book folder rag dust - item
  )
  (:predicates
    (at ?e - locatable ?l - location)
    (on_top ?top - item ?bottom - locatable)
    (in ?o - item ?c - container)
    (covered ?e - locatable ?d - dust)
    (holding ?r - robot ?o - item)
    (robot_free ?r - robot)
    (opened ?c - container)
  )

  (:action drive
    :parameters (?r - robot ?from - location ?to - location)
    :precondition (at ?r ?from)
    :effect (and (not (at ?r ?from)) (at ?r ?to))
  )

  (:action pick
    :parameters (?r - robot ?o - item ?s - locatable ?l - location)
    :precondition (and (at ?r ?l) (at ?s ?l) (on_top ?o ?s) (robot_free ?r))
    :effect (and (holding ?r ?o) (not (on_top ?o ?s)) (not (robot_free ?r)))
  )

  (:action place
    :parameters (?r - robot ?o - item ?s - locatable ?l - location)
    :precondition (and (at ?r ?l) (at ?s ?l) (holding ?r ?o))
    :effect (and (on_top ?o ?s) (robot_free ?r) (not (holding ?r ?o)))
  )

  (:action open
    :parameters (?r - robot ?c - container ?l - location)
    :precondition (and (at ?r ?l) (at ?c ?l) (robot_free ?r) (not (opened ?c)))
    :effect (opened ?c)
  )

  (:action place_in_container
    :parameters (?r - robot ?o - item ?c - container ?l - location)
    :precondition (and (at ?r ?l) (at ?c ?l) (holding ?r ?o) (opened ?c))
    :effect (and (in ?o ?c) (robot_free ?r) (not (holding ?r ?o)))
  )

  (:action clean
    :parameters (?r - robot ?g - rag ?e - locatable ?d - dust ?l - location)
    :precondition (and (at ?r ?l) (at ?e ?l) (holding ?r ?g) (covered ?e ?d))
    :effect (not (covered ?e ?d))
  )
)
