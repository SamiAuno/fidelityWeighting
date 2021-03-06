# -*- coding: utf-8 -*-
"""
Created on Fri Jul 21 16:31:20 2017

Generate fidelity weighting vector

@author: Santeri Rouhinen
"""

import scipy
from scipy import asmatrix, genfromtxt, signal
from scipy.linalg import norm
from scipy.random import randn


"""Load source identities, forward model, and inverse operators."""
fpath = '/some/directory'
fname_source_identities = fpath + '/sourceIdentities.csv'
fname_forward_operator = fpath + '/forwardSolution.csv'
fname_inverse_operator = fpath + '/inverseSolution.csv'

"""Expected ids for parcels are 0 to n-1, where n is number of parcels,
and -1 for sources that do not belong to any parcel."""
sourceIdentities = genfromtxt(fname_source_identities, dtype='int32',
                              delimiter=',')

"""Zero as ID doesn't work if parcel not belonging to any parcel is given
zero value. There could be sources not in any parcel. Sparce parcels that
is. Should initialize those to -1 or Nan."""
# sensors x sources
forwardOperator = scipy.matrix(genfromtxt(fname_forward_operator,
                                          dtype='float', delimiter=','))

# sources x sensors
inverseOperator = scipy.matrix(genfromtxt(fname_inverse_operator,
                                          dtype='float', delimiter=','))


"""Generate oscillatory parcel signals."""
n_parcels = max(sourceIdentities) + 1  # Maybe one should test if unique non-negative values == max+1. This is expected in the code.

time_output = 30000   # Samples. Peaks at about 20 GB ram with 30 000 samples. Using too few samples will give poor results.
time_cut = 20    # Samples to remove from ends to get rid of border effects
time_generate = time_output + 2*time_cut


widths = scipy.arange(5, 6)     # Original values 1, 31. Higher number wider span.
parcelTimeSeries = randn(n_parcels, time_generate)  # Generate random signal

for i in range(n_parcels):
    parcelTimeSeries[i] = signal.cwt(parcelTimeSeries[i], signal.ricker, widths)     # Mexican hat continuous wavelet transform random series.

parcelTimeSeries = signal.hilbert(parcelTimeSeries)     # Hilbert transform. Get analytic signal.
parcelTimeSeries = parcelTimeSeries[:, time_cut:-time_cut]    # Cut off borders




"""Clone parcel time series to source time series."""
sourceTimeSeries = scipy.zeros((len(sourceIdentities), int(parcelTimeSeries.shape[1])), dtype='complex')  # Zeros (complex) sources x samples

for i, identity in enumerate(sourceIdentities):              # i-teration and identity
    if (identity > -1):                                       # -1 as identity means source does not belong to any parcel. Other negative values should not really be there.
        sourceTimeSeries[i] = parcelTimeSeries[identity]    # Clone parcel time series to source space. 

checkSourceTimeSeries = scipy.real(sourceTimeSeries[:])    # For checking



"""Forward then inverse model source series."""
sourceTimeSeries = inverseOperator*(forwardOperator * sourceTimeSeries)


"""Change to amplitude 1, keep angle using Euler's formula."""
sourceTimeSeries = scipy.exp(1j*(asmatrix(scipy.angle(sourceTimeSeries))))
parcelTimeSeries = scipy.exp(1j*(asmatrix(scipy.angle(parcelTimeSeries))))


"""Get cPLV needed for flips and weighting."""
cPLVArray = scipy.zeros(len(sourceIdentities), dtype='complex')   # Initialize as zeros (complex). 

for i, identity in enumerate(sourceIdentities):              # Compute cPLV only of parcel source pairs of sources that belong to that parcel. One source belong to only one parcel.
    if (sourceIdentities[i] >= 0):     # Don't compute negative values. These should be sources not belonging to any parcel.
        cPLVArray[i] = scipy.sum((scipy.asarray(parcelTimeSeries[identity])) * scipy.conjugate(scipy.asarray(sourceTimeSeries[i])))

cPLVArray /= time_output    # Normalize by samples. For debugging. Output doesn't change even if you don't do this.


"""Get weights and flip. This could be the output."""
weights = scipy.zeros(len(sourceIdentities))    # Initialize as zeros

for i,cPLV in enumerate(cPLVArray):
    weights[i] = scipy.real(cPLV)**2 * scipy.sign(scipy.real(cPLV))     # Sign is the flip; weight (real part)^2


"""Create weighted inverse operator and normalize the norm of weighted inv op
to match original inv op's norm."""
weightedInvOp = scipy.eye(weights.shape[0]) * weights * inverseOperator      # Multiply sensor dimension in inverseOperator by weight. This one would be the un-normalized operator.

weightsNormalized = scipy.zeros(len(weights))  # Initialize norm normalized weights. Maybe not necessary.
for parcel in range(n_parcels):       # Normalize parcel level norms. 
    ii = [i for i, source in enumerate(sourceIdentities) if source == parcel]    # Index sources belonging to parcel
    weightsNormalized[ii] = weights[ii] * (norm(inverseOperator[ii]) / norm(weightedInvOp[ii]))   # Normalize per parcel.

weightedInvOp = scipy.eye(weightsNormalized.shape[0])*weightsNormalized * inverseOperator   # Parcel level normalized operator.
weightedInvOp *= norm(inverseOperator) / norm(scipy.nan_to_num(weightedInvOp))   # Operator level normalized operator. If there are sources not in any parcel weightedInvOp gets Nan values due to normalizations.
weightedInvOp = scipy.nan_to_num(weightedInvOp)


"""Check if weighting worked.

Do correlations between the original time series and the weighted inverse
and normal inverse models.

Make parcel and sensor time series. Separate series to avoid overfitted
estimation.
"""
samplesSubset = 10000 + 2*time_cut

checkParcelTimeSeries = randn(n_parcels, samplesSubset)  # Generate random signal

for i in range(n_parcels):
    checkParcelTimeSeries[i] = signal.cwt(checkParcelTimeSeries[i], signal.ricker, widths)     # Mexican hat continuous wavelet transform random series.

checkParcelTimeSeries = signal.hilbert(checkParcelTimeSeries)     # Hilbert transform. Get analytic signal.
checkParcelTimeSeries = checkParcelTimeSeries[:, time_cut:-time_cut]    # Cut off borders

# Change to amplitude 1, keep angle using Euler's formula.
checkParcelTimeSeries = scipy.exp(1j*(asmatrix(scipy.angle(checkParcelTimeSeries))))



## Clone parcel time series to source time series
checkSourceTimeSeries = scipy.zeros((len(sourceIdentities), int(checkParcelTimeSeries.shape[1])), dtype='complex')  # Zeros (complex) sources x samples

for i,identity in enumerate(sourceIdentities):              # i-teration and identity
    if (identity > -1):                                       # -1 as identity means source does not belong to any parcel. Other negative values should not really be there.
        checkSourceTimeSeries[i] = checkParcelTimeSeries[identity]    # Clone parcel time series to source space. 

sensorTimeSeries = forwardOperator * checkSourceTimeSeries


"""Correlations between inversed sensorTimeSeries and sourceTimeSeries. Use
only a time subset as the memory use is quite large."""

# Binary matrix of sources belonging to parcels
sourceParcelMatrix = scipy.zeros((n_parcels, len(sourceIdentities)), dtype=scipy.int8)
for i,identity in enumerate(sourceIdentities):
    if (identity >= 0):     # Don't place negative values. These should be sources not belonging to any parcel.
        sourceParcelMatrix[identity, i] = 1


parcelPLVW = scipy.zeros(n_parcels, dtype=scipy.float32)  # For the weighted inverse operator
parcelPLVO = scipy.zeros(n_parcels, dtype=scipy.float32)  # For the original inverse operator


estimatedSourceSeriesW = weightedInvOp   * sensorTimeSeries     # Weighted and original estimated source time series
estimatedSourceSeriesO = inverseOperator * sensorTimeSeries

"""Change to amplitude 1, keep angle using Euler's formula."""
estimatedSourceSeriesW = scipy.exp(1j*(asmatrix(scipy.angle(estimatedSourceSeriesW))))
estimatedSourceSeriesO = scipy.exp(1j*(asmatrix(scipy.angle(estimatedSourceSeriesO))))


for i in range(n_parcels):
    A = scipy.ravel(checkParcelTimeSeries[i, :])                                        # True simulated parcel time series
    nSources = scipy.sum(sourceParcelMatrix[i, :])
    B = scipy.ravel((sourceParcelMatrix[i, :]) * estimatedSourceSeriesW) / nSources      # Estimated      parcel time series
    C = scipy.ravel((sourceParcelMatrix[i, :]) * estimatedSourceSeriesO) / nSources
    parcelPLVW[i] = scipy.mean(A * scipy.conjugate(B))
    parcelPLVO[i] = scipy.mean(A * scipy.conjugate(C))


