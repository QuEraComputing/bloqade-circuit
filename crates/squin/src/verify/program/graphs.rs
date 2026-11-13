//! Answer the questions that the verifier rules ask about `circuit` graphs.

use kirin::prelude::*;

use super::Program;
use crate::ir::query;

impl<'a> Program<'a> {
    /// Return the dataflow graphs that `statement` owns.
    pub(in crate::verify) fn graphs(
        self,
        statement: Statement,
    ) -> impl Iterator<Item = DiGraph> + 'a {
        statement.definition(self.stage).digraphs().copied()
    }

    /// Return the dataflow graphs that the statements of `blocks` own.
    pub(in crate::verify) fn graphs_in(self, blocks: &[Block]) -> Vec<DiGraph> {
        query::graphs(self.stage, blocks)
    }

    /// Return the nodes of `graph` with each node after the nodes that it reads.
    pub(in crate::verify) fn nodes(self, graph: DiGraph) -> Vec<Statement> {
        // The scope check reports a cycle first. The other rules then read
        // the nodes in statement order.
        let members = || graph.expect_info(self.stage).nodes().collect();
        query::graph_order(self.stage, graph).unwrap_or_else(members)
    }

    /// Tell whether the nodes of `graph` read each other in a cycle.
    pub(in crate::verify) fn has_cycle(self, graph: DiGraph) -> bool {
        query::graph_order(self.stage, graph).is_none()
    }

    /// Return the ports of `graph`, in order.
    pub(in crate::verify) fn ports(self, graph: DiGraph) -> Vec<SSAValue> {
        let ports = graph.expect_info(self.stage).ports();
        ports.iter().map(|port| (*port).into()).collect()
    }

    /// Return the capture ports of `graph`, in order.
    pub(in crate::verify) fn capture_ports(self, graph: DiGraph) -> Vec<SSAValue> {
        let ports = graph.expect_info(self.stage).capture_ports();
        ports.iter().map(|port| (*port).into()).collect()
    }

    /// Return the ports of `graph` and the results of its nodes.
    pub(in crate::verify) fn graph_definitions(self, graph: DiGraph) -> Vec<SSAValue> {
        let results = self
            .nodes(graph)
            .into_iter()
            .flat_map(move |node| self.results(node));
        self.ports(graph).into_iter().chain(results).collect()
    }

    /// Name `statement` by a value that it defines or reads, for a report.
    pub(in crate::verify) fn describe(self, statement: Statement) -> String {
        if let Some(result) = self.results(statement).next() {
            return format!("The statement that defines {}", self.named(result));
        }
        match self.operands(statement).next() {
            Some(operand) => format!("The statement that reads {}", self.named(operand)),
            None => "A statement without values".to_string(),
        }
    }

    /// Return the values that the graph `graph` yields, in order.
    pub(in crate::verify) fn graph_yields(self, graph: DiGraph) -> Vec<SSAValue> {
        graph.expect_info(self.stage).yields().to_vec()
    }

    /// Return the graph and the position of the port `value`.
    pub(in crate::verify) fn port(self, value: SSAValue) -> Option<(DiGraph, usize)> {
        match *value.expect_info(self.stage).kind() {
            SSAKind::Port(PortParent::DiGraph(graph), position) => Some((graph, position)),
            _ => None,
        }
    }
}
