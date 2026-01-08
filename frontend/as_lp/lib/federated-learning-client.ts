/**
 * Federated Learning Client for Privacy-Preserving Anomaly Detection
 *
 * This client enables distributed training of anomaly detection models
 * across multiple nodes without sharing raw telemetry data.
 */

import { useState, useEffect, useCallback, useRef } from 'react';

export interface FederatedModelUpdate {
  nodeId: string;
  modelVersion: number;
  weights: number[][];
  gradients: number[][];
  sampleCount: number;
  timestamp: number;
  checksum: string;
}

export interface FederatedTrainingMetrics {
  localAccuracy: number;
  localLoss: number;
  globalAccuracy: number;
  globalLoss: number;
  roundsCompleted: number;
  totalSamples: number;
}

export interface FederatedLearningConfig {
  nodeId: string;
  learningRate: number;
  batchSize: number;
  epochs: number;
  privacyBudget: number;
  aggregationRounds: number;
  minNodesForAggregation: number;
}

export class FederatedLearningClient {
  private config: FederatedLearningConfig;
  private localModel: number[][] = [];
  private trainingData: number[][] = [];
  private isTraining = false;
  private currentRound = 0;

  constructor(config: FederatedLearningConfig) {
    this.config = config;
    this.initializeLocalModel();
  }

  private initializeLocalModel(): void {
    // Initialize a simple neural network for anomaly detection
    // Input: 3 features (voltage, temperature, gyro)
    // Hidden: 8 neurons
    // Output: 1 (anomaly score)
    this.localModel = [
      // Input to hidden weights (3x8)
      [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8],
      [-0.1, -0.2, -0.3, -0.4, -0.5, -0.6, -0.7, -0.8],
      [0.05, -0.05, 0.1, -0.1, 0.15, -0.15, 0.2, -0.2],
      // Hidden to output weights (8x1)
      [0.3, -0.2, 0.1, -0.4, 0.5, -0.3, 0.2, -0.1]
    ];
  }

  public addTrainingSample(features: number[]): void {
    this.trainingData.push([...features]);
  }

  public async trainLocalModel(): Promise<FederatedTrainingMetrics> {
    if (this.isTraining) {
      throw new Error('Training already in progress');
    }

    this.isTraining = true;
    const startTime = Date.now();

    try {
      const metrics = await this.performLocalTraining();
      this.currentRound++;
      return metrics;
    } finally {
      this.isTraining = false;
    }
  }

  private async performLocalTraining(): Promise<FederatedTrainingMetrics> {
    const { learningRate, batchSize, epochs } = this.config;
    let totalLoss = 0;
    let correctPredictions = 0;

    for (let epoch = 0; epoch < epochs; epoch++) {
      // Shuffle training data
      const shuffledData = [...this.trainingData].sort(() => Math.random() - 0.5);

      for (let i = 0; i < shuffledData.length; i += batchSize) {
        const batch = shuffledData.slice(i, i + batchSize);
        const batchLoss = this.trainOnBatch(batch, learningRate);
        totalLoss += batchLoss;

        // Calculate accuracy on batch
        for (const sample of batch) {
          const prediction = this.predict(sample.slice(0, 3));
          const actual = sample[3]; // Assume last element is anomaly label
          if ((prediction > 0.5) === (actual > 0.5)) {
            correctPredictions++;
          }
        }
      }
    }

    const localAccuracy = correctPredictions / (this.trainingData.length * epochs);
    const localLoss = totalLoss / (this.trainingData.length * epochs);

    return {
      localAccuracy,
      localLoss,
      globalAccuracy: 0, // Will be updated after aggregation
      globalLoss: 0, // Will be updated after aggregation
      roundsCompleted: this.currentRound,
      totalSamples: this.trainingData.length
    };
  }

  private trainOnBatch(batch: number[][], learningRate: number): number {
    let batchLoss = 0;

    for (const sample of batch) {
      const features = sample.slice(0, 3);
      const target = sample[3];

      // Forward pass
      const prediction = this.predict(features);
      const loss = this.computeLoss(prediction, target);
      batchLoss += loss;

      // Backward pass (simplified gradient descent)
      const gradient = this.computeGradient(prediction, target);
      this.updateWeights(features, gradient, learningRate);
    }

    return batchLoss / batch.length;
  }

  private predict(features: number[]): number {
    // Simple neural network forward pass
    const hidden = features.map((f, i) =>
      Math.tanh(features.reduce((sum, feat, j) => sum + feat * this.localModel[i][j], 0))
    );

    const output = hidden.reduce((sum, h, i) => sum + h * this.localModel[3][i], 0);
    return 1 / (1 + Math.exp(-output)); // Sigmoid activation
  }

  private computeLoss(prediction: number, target: number): number {
    // Binary cross-entropy loss
    const epsilon = 1e-15;
    const pred = Math.max(epsilon, Math.min(1 - epsilon, prediction));
    return -(target * Math.log(pred) + (1 - target) * Math.log(1 - pred));
  }

  private computeGradient(prediction: number, target: number): number {
    return prediction - target;
  }

  private updateWeights(features: number[], gradient: number, learningRate: number): void {
    // Update weights using gradient descent
    for (let i = 0; i < this.localModel.length; i++) {
      for (let j = 0; j < this.localModel[i].length; j++) {
        if (i < 3) {
          // Input to hidden weights
          this.localModel[i][j] -= learningRate * gradient * features[i] * features[j];
        } else {
          // Hidden to output weights
          const hiddenActivation = Math.tanh(features.reduce((sum, f, k) => sum + f * this.localModel[k][j], 0));
          this.localModel[i][j] -= learningRate * gradient * hiddenActivation;
        }
      }
    }
  }

  public generateModelUpdate(): FederatedModelUpdate {
    // Add noise for differential privacy
    const noisyWeights = this.addDifferentialPrivacy(this.localModel);

    return {
      nodeId: this.config.nodeId,
      modelVersion: this.currentRound,
      weights: noisyWeights,
      gradients: this.computeGradients(),
      sampleCount: this.trainingData.length,
      timestamp: Date.now(),
      checksum: this.computeChecksum(noisyWeights)
    };
  }

  private addDifferentialPrivacy(weights: number[][]): number[][] {
    const { privacyBudget } = this.config;
    const noiseScale = 1.0 / privacyBudget;

    return weights.map(layer =>
      layer.map(weight => weight + (Math.random() - 0.5) * noiseScale)
    );
  }

  private computeGradients(): number[][] {
    // Compute gradients for federated averaging
    // This is a simplified version - in practice, you'd store gradients during training
    return this.localModel.map(layer =>
      layer.map(() => Math.random() * 0.1 - 0.05) // Random gradients for demo
    );
  }

  private computeChecksum(weights: number[][]): string {
    const data = weights.flat().join(',');
    let hash = 0;
    for (let i = 0; i < data.length; i++) {
      const char = data.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return hash.toString(16);
  }

  public updateGlobalModel(globalWeights: number[][]): void {
    // Federated averaging: combine local and global models
    const alpha = 0.1; // Learning rate for global model update
    this.localModel = this.localModel.map((layer, i) =>
      layer.map((weight, j) => weight + alpha * (globalWeights[i][j] - weight))
    );
  }

  public getTrainingStatus() {
    return {
      isTraining: this.isTraining,
      currentRound: this.currentRound,
      samplesCollected: this.trainingData.length,
      modelInitialized: this.localModel.length > 0
    };
  }

  public clearTrainingData(): void {
    this.trainingData = [];
  }
}