from __future__ import print_function, division, absolute_import

from numba.core.compiler_machinery import PassManager

from numba.core.untyped_passes import (
    ExtractByteCode,
    TranslateByteCode,
    FixupArgs,
    IRProcessing,
    DeadBranchPrune,
    RewriteSemanticConstants,
    InlineClosureLikes,
    GenericRewrites,
    WithLifting,
    InlineInlinables,
    FindLiterallyCalls,
    MakeFunctionToJitFunction,
    CanonicalizeLoopExit,
    CanonicalizeLoopEntry,
    ReconstructSSA,
    LiteralUnroll,
)

from numba.core.typed_passes import (
    NopythonTypeInference,
    AnnotateTypes,
    NopythonRewrites,
    PreParforPass,
    ParforPass,
    DumpParforDiagnostics,
    IRLegalization,
    InlineOverloads,
    PreLowerStripPhis,
)

from .dppy_passes import (
    DPPYConstantSizeStaticLocalMemoryPass,
    DPPYPreParforPass,
    DPPYParforPass,
    SpirvFriendlyLowering,
    DPPYNoPythonBackend,
    DPPYDumpParforDiagnostics,
)

from .rename_numpy_functions_pass import (
    DPPYRewriteOverloadedNumPyFunctions,
    DPPYRewriteNdarrayFunctions,
)


class DPPYPassBuilder(object):
    """
    This is the DPPY pass builder to run Intel GPU/CPU specific
    code-generation and optimization passes. This pass builder does
    not offer objectmode and interpreted passes.
    """

    @staticmethod
    def default_numba_nopython_pipeline(state, pm):
        """Adds the default set of NUMBA passes to the pass manager"""
        if state.func_ir is None:
            pm.add_pass(TranslateByteCode, "analyzing bytecode")
            pm.add_pass(FixupArgs, "fix up args")
        pm.add_pass(IRProcessing, "processing IR")
        pm.add_pass(WithLifting, "Handle with contexts")

        # this pass rewrites name of NumPy functions we intend to overload
        pm.add_pass(
            DPPYRewriteOverloadedNumPyFunctions,
            "Rewrite name of Numpy functions to overload already overloaded function",
        )

        # Add pass to ensure when users are allocating static
        # constant memory the size is a constant and can not
        # come from a closure variable
        pm.add_pass(
            DPPYConstantSizeStaticLocalMemoryPass,
            "dppy constant size for static local memory",
        )

        # pre typing
        if not state.flags.no_rewrites:
            pm.add_pass(RewriteSemanticConstants, "rewrite semantic constants")
            pm.add_pass(DeadBranchPrune, "dead branch pruning")
            pm.add_pass(GenericRewrites, "nopython rewrites")

        pm.add_pass(InlineClosureLikes, "inline calls to locally defined closures")
        # convert any remaining closures into functions
        pm.add_pass(
            MakeFunctionToJitFunction, "convert make_function into JIT functions"
        )
        # inline functions that have been determined as inlinable and rerun
        # branch pruning, this needs to be run after closures are inlined as
        # the IR repr of a closure masks call sites if an inlinable is called
        # inside a closure
        pm.add_pass(InlineInlinables, "inline inlinable functions")
        if not state.flags.no_rewrites:
            pm.add_pass(DeadBranchPrune, "dead branch pruning")

        pm.add_pass(FindLiterallyCalls, "find literally calls")
        pm.add_pass(LiteralUnroll, "handles literal_unroll")

        if state.flags.enable_ssa:
            pm.add_pass(ReconstructSSA, "ssa")
        # typing
        pm.add_pass(NopythonTypeInference, "nopython frontend")
        pm.add_pass(AnnotateTypes, "annotate types")

        pm.add_pass(
            DPPYRewriteNdarrayFunctions,
            "Rewrite ndarray functions to dppy supported functions",
        )

        # strip phis
        pm.add_pass(PreLowerStripPhis, "remove phis nodes")

        # optimisation
        pm.add_pass(InlineOverloads, "inline overloaded functions")

    @staticmethod
    def define_nopython_pipeline(state, name="dppy_nopython"):
        """Returns an nopython mode pipeline based PassManager"""
        pm = PassManager(name)
        DPPYPassBuilder.default_numba_nopython_pipeline(state, pm)

        # Intel GPU/CPU specific optimizations
        pm.add_pass(DPPYPreParforPass, "Preprocessing for parfors")
        if not state.flags.no_rewrites:
            pm.add_pass(NopythonRewrites, "nopython rewrites")
        pm.add_pass(DPPYParforPass, "convert to parfors")

        # legalise
        pm.add_pass(IRLegalization, "ensure IR is legal prior to lowering")

        # lower
        pm.add_pass(SpirvFriendlyLowering, "SPIRV-friendly lowering pass")
        pm.add_pass(DPPYNoPythonBackend, "nopython mode backend")
        pm.add_pass(DPPYDumpParforDiagnostics, "dump parfor diagnostics")
        pm.finalize()
        return pm
