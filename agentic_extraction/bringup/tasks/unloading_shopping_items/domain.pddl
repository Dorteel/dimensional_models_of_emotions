(define (domain domain_pddl)
    (:requirements :negative-preconditions :typing)
    (:types
        locatable - object
        location - object
        robot - locatable
        item - locatable
        container - item
        furniture - locatable
        carton - container
        cabinet - container
        bottle_of_lotion - item
        bottle_of_detergent - item
        picture_frame - item
        notebook - item
        painting - item
        plastic_art - item
        lampshade - item
        globe - item
        console_table - furniture
        floor - furniture
    )
    (:predicates
        (at ?e - locatable ?l - location)
        (in ?o - item ?c - container)
        (on_top ?top - item ?bottom - locatable)
        (next_to ?a - item ?b - locatable)
        (holding ?a - robot ?o - item)
        (robot_free ?r - robot)
    )

    ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;; ACTION ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

    (:action drive
    :parameters (?r - robot ?from - location ?to - location)
    :precondition
        (and
            (at ?r ?from)
        )
    :effect
        (and
            (not (at ?r ?from))
            (at ?r ?to)
        )
)

(:action pick
    :parameters (?r - robot ?o - item ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (at ?o ?l)
            (robot_free ?r)
        )
    :effect
        (and
            (not (at ?o ?l))
            (holding ?r ?o)
            (not (robot_free ?r))
        )
)

(:action place
    :parameters (?r - robot ?o - item ?support - locatable ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (holding ?r ?o)
            (at ?support ?l)
        )
    :effect
        (and
            (not (holding ?r ?o))
            (robot_free ?r)
            (on_top ?o ?support)
        )
)

(:action place_next_to
    :parameters (?r - robot ?o - item ?target - locatable ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (holding ?r ?o)
            (at ?target ?l)
        )
    :effect
        (and
            (not (holding ?r ?o))
            (robot_free ?r)
            (next_to ?o ?target)
        )
)
)
