(define (domain domain_pddl)
    (:requirements :negative-preconditions :typing)
    (:types
        locatable - object
        location - object
        robot - locatable
        item - locatable
        device - item
        furniture - locatable
        residue - item
        dust - residue
        floor - furniture
        vacuum - device
    )
    (:predicates
        (at ?e - locatable ?l - location)
        (on_top ?top - item ?bottom - locatable)
        (holding ?a - robot ?o - item)
        (robot_free ?r - robot)
        (covered ?o - locatable ?s - residue)
    )

    ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;; ACTION ;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

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
            (holding ?r ?o)
            (not (at ?o ?l))
            (not (robot_free ?r))
        )
)

(:action clean
    :parameters (?r - robot ?v - vacuum ?o - locatable ?d - dust ?l - location)
    :precondition
        (and
            (at ?r ?l)
            (holding ?r ?v)
            (covered ?o ?d)
        )
    :effect
        (and
            (not (covered ?o ?d))
        )
)
)
