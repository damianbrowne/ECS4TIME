# Besides some added methods, most of this class was written by Iain Barr (ijmbarr on GitHub)
# from his public repository, causalgraphicalmodels
# The code has been imported and modified into this project for ease/consistency

import inspect
import os
import util
import math
import gutil

from scm import StructuralCausalModel
from cgm import CausalGraph
from assignment_models import AssignmentModel, ActionModel, DiscreteModel, RandomModel


class Environment:
    def __init__(self, assignment, rew_var="Y"):
        """
        Creates StructuralCausalModel from assignment of the form
        { variable: Function(parents) }
        """
        self.domains = {}
        self._assignment = assignment.copy()
        nodes = list(assignment.keys())
        self.act_vars = []
        self.rew_var = rew_var
        set_nodes = []
        edges = []

        for node, model in assignment.items():
            if model is None:
                set_nodes.append(node)

            elif isinstance(model, AssignmentModel):
                self.domains[node] = model.domain
                if isinstance(model, ActionModel):
                  self.act_vars.append(node)
                edges.extend([
                    (parent, node)
                    for parent in model.parents
                ])

            elif callable(model):
                sig = inspect.signature(model)
                parents = [
                    parent
                    for parent in sig.parameters.keys()
                    if parent != "n_samples"
                ]
                self._assignment[node] = AssignmentModel(parents, model)
                edges.extend([(p, node) for p in parents])

            else:
                raise ValueError("Model must be either callable or None. "
                                 "Instead got {} for node {}."
                                 .format(model, node))

        self.cgm = CausalGraph(nodes=nodes, edges=edges, set_nodes=set_nodes)

        pre_nodes = []
        [pre_nodes.extend(self.cgm.get_ancestors(v)) for v in self.act_vars]
        self.pre = StructuralCausalModel(gutil.only_given_keys(self._assignment, pre_nodes))
        post_ass = self._assignment.copy()
        [post_ass.update({n: ActionModel(self.cgm.get_parents(n), self.domains[n])}) for n in pre_nodes]
        self.post = StructuralCausalModel(post_ass)
        
        self.feature_nodes = []
        [self.feature_nodes.extend(self.cgm.get_parents(n)) for n in self.act_vars]
        gutil.remove_dupes(self.feature_nodes)
        self.action_rewards = self.get_action_rewards()
  
    def get_action_rewards(self, iterations=750):
      act_feat_nodes = self.act_vars + self.feature_nodes
      gutil.remove_dupes(act_feat_nodes)
      perms = gutil.permutations(gutil.only_given_keys(self.domains, act_feat_nodes))
      action_rewards = []
      for p in perms:
        action_reward = [p,0]
        for _ in range(iterations):
          action_reward[1] += self.post.sample(p)[self.rew_var]
        action_reward[1] /= iterations
        action_rewards.append(tuple(action_reward))
      return action_rewards
    
    def optimal_action_rewards(self, givens={}):
      action_rewards = []
      for tup in self.action_rewards:
        action_rewards.append((gutil.only_given_keys(tup[0], self.act_vars), tup[1]))
        for key in givens:
          if tup[0][key] != givens[key]:
            action_rewards = action_rewards[:-1]
            break
      best_rew = -math.inf
      best = []
      for tup in action_rewards:
        best = [tup] if tup[1] > best_rew else best + [tup] if tup[1] == best_rew else best
        best_rew = max(best_rew, tup[1])
      return best
    
    def optimal_actions(self, givens={}):
      return [tup[0] for tup in self.optimal_action_rewards(givens)]
    
    def optimal_reward(self, givens={}):
      return self.optimal_action_rewards(givens)[0][1]
    
    def selection_diagram(self, s_node_children):
      return self.cgm.selection_diagram(s_node_children)

    def __repr__(self):
      variables = ", ".join(map(str, sorted(self.cgm.dag.nodes())))
      return ("{classname}({vars})"
          .format(classname=self.__class__.__name__,
              vars=variables))

    def __hash__(self):
      return hash(gutil.dict_to_tuple_list(self._assignment))

    def __eq__(self, other):
      if not isinstance(other, self.__class__) \
          or self.rew_var != other.rew_var \
          or self._assignment.keys() != other._assignment.keys():
        return False
      for var in self._assignment:
        if self._assignment[var] != other._assignment[var]:
          return False
      return True

if __name__ == "__main__":
    # domains = {"W": (0,1), "X": (0,1), "Z": (0,1), "Y": (0,1)}
    universal_model = Environment({
    "W": RandomModel((0.5, 0.5)),
    "X": ActionModel(("W"), (0, 1)),
    "Z": DiscreteModel(("X"), {(0,): (0.75, 0.25), (1,): (0.25, 0.75)}),
    "Y": DiscreteModel(("W", "Z"), {(0, 0): (1, 0), (0, 1): (1, 0), (1, 0): (1, 0), (1, 1): (0, 1)})
  })
    # print(universal_model.sample({"X": 1}))
    # print(universal_model.cgm.get_ancestors("Y"))
    # print(universal_model.pre.sample())
    # print(universal_model.post.sample(set_values={"W": 1, "X": 1}))
    # print(universal_model._assignment["W"].model)
    # print(universal_model.get_action_rewards())
    print(universal_model.optimal_action_rewards({"W":1}))
    # print(universal_model.optimal_act_rew({"W":1}))
