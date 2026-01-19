"use client"

import React, { useState, useCallback } from 'react'
import { DragDropContext, Droppable, Draggable, DropResult } from '@hello-pangea/dnd'
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Play, Save, RotateCcw, Plus, Trash2, Settings, Eye } from 'lucide-react'
import { toast } from "sonner"

interface PolicyElement {
  id: string
  type: 'condition' | 'action' | 'phase'
  name: string
  config: Record<string, any>
}

interface Policy {
  id: string
  name: string
  description: string
  elements: PolicyElement[]
  validationErrors: string[]
}

const AVAILABLE_ACTIONS = [
  'LOG_EVENT', 'MONITOR', 'ALERT_ONLY', 'RESTART_SERVICE', 'THERMAL_REGULATION',
  'POWER_LOAD_BALANCING', 'STABILIZATION', 'SAFE_MODE', 'PING_GROUND',
  'DEPLOY_SOLAR_PANELS', 'FIRE_THRUSTERS', 'PAYLOAD_OPERATIONS',
  'HIGH_POWER_TRANSMISSION', 'ISOLATE_SUBSYSTEM', 'ENTER_SAFE_MODE'
]

const MISSION_PHASES = [
  'LAUNCH', 'NOMINAL_OPS', 'SAFE_MODE', 'RECOVERY', 'MAINTENANCE'
]

const CONDITION_TYPES = [
  'severity >= threshold',
  'recurrence_count >= count',
  'component_health == status',
  'resource_usage > percentage',
  'time_since_last_action > seconds'
]

export function VisualPolicyBuilder() {
  const [policies, setPolicies] = useState<Policy[]>([
    {
      id: 'default-policy',
      name: 'Default Recovery Policy',
      description: 'Basic recovery policy for common anomalies',
      elements: [],
      validationErrors: []
    }
  ])

  const [activePolicy, setActivePolicy] = useState<string>('default-policy')
  const [isSimulating, setIsSimulating] = useState(false)
  const [simulationResults, setSimulationResults] = useState<any>(null)

  const currentPolicy = policies.find(p => p.id === activePolicy)!

  const addElement = useCallback((type: PolicyElement['type'], template?: Partial<PolicyElement>) => {
    const newElement: PolicyElement = {
      id: `${type}-${Date.now()}`,
      type,
      name: template?.name || `${type.charAt(0).toUpperCase() + type.slice(1)} ${currentPolicy.elements.length + 1}`,
      config: template?.config || getDefaultConfig(type)
    }

    setPolicies(prev => prev.map(policy =>
      policy.id === activePolicy
        ? { ...policy, elements: [...policy.elements, newElement] }
        : policy
    ))
  }, [activePolicy, currentPolicy.elements.length])

  const updateElement = useCallback((elementId: string, updates: Partial<PolicyElement>) => {
    setPolicies(prev => prev.map(policy =>
      policy.id === activePolicy
        ? {
            ...policy,
            elements: policy.elements.map(el =>
              el.id === elementId ? { ...el, ...updates } : el
            )
          }
        : policy
    ))
  }, [activePolicy])

  const removeElement = useCallback((elementId: string) => {
    setPolicies(prev => prev.map(policy =>
      policy.id === activePolicy
        ? { ...policy, elements: policy.elements.filter(el => el.id !== elementId) }
        : policy
    ))
  }, [activePolicy])

  const onDragEnd = useCallback((result: DropResult) => {
    if (!result.destination) return

    const elements = Array.from(currentPolicy.elements)
    const [reorderedItem] = elements.splice(result.source.index, 1)
    elements.splice(result.destination.index, 0, reorderedItem)

    setPolicies(prev => prev.map(policy =>
      policy.id === activePolicy
        ? { ...policy, elements }
        : policy
    ))
  }, [activePolicy, currentPolicy.elements])

  const validatePolicy = useCallback(() => {
    const errors: string[] = []

    if (currentPolicy.elements.length === 0) {
      errors.push('Policy must contain at least one element')
    }

    // Check for logical flow
    const hasCondition = currentPolicy.elements.some(el => el.type === 'condition')
    const hasAction = currentPolicy.elements.some(el => el.type === 'action')

    if (!hasCondition && !hasAction) {
      errors.push('Policy should contain conditions and/or actions')
    }

    // Validate element configurations
    currentPolicy.elements.forEach((element, index) => {
      if (element.type === 'condition' && !element.config.condition) {
        errors.push(`Condition ${index + 1} is missing condition expression`)
      }
      if (element.type === 'action' && !element.config.action) {
        errors.push(`Action ${index + 1} is missing action type`)
      }
    })

    setPolicies(prev => prev.map(policy =>
      policy.id === activePolicy
        ? { ...policy, validationErrors: errors }
        : policy
    ))

    return errors.length === 0
  }, [activePolicy, currentPolicy])

  const simulatePolicy = useCallback(async () => {
    setIsSimulating(true)
    try {
      // Mock simulation - in real implementation, this would call the backend
      const mockAnomaly = {
        type: 'power_fault',
        severity: 0.85,
        recurrence_count: 1,
        component_health: 'degraded',
        resource_usage: 75
      }

      const results = {
        anomaly: mockAnomaly,
        triggeredElements: currentPolicy.elements.filter(element => {
          if (element.type === 'condition') {
            return evaluateCondition(element.config.condition, mockAnomaly)
          }
          return true
        }),
        actionsExecuted: [],
        validationPassed: validatePolicy()
      }

      setSimulationResults(results)
      toast.success('Policy simulation completed')
    } catch (error) {
      toast.error('Simulation failed')
    } finally {
      setIsSimulating(false)
    }
  }, [currentPolicy, validatePolicy])

  const savePolicy = useCallback(() => {
    if (!validatePolicy()) {
      toast.error('Please fix validation errors before saving')
      return
    }

    // In real implementation, this would save to backend
    toast.success('Policy saved successfully')
  }, [validatePolicy])

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Visual Policy Builder
          </h1>
          <p className="text-gray-600 dark:text-gray-300">
            Create and manage recovery policies with drag-and-drop interface
          </p>
        </div>

        <Tabs value={activePolicy} onValueChange={setActivePolicy} className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            {policies.map(policy => (
              <TabsTrigger key={policy.id} value={policy.id}>
                {policy.name}
              </TabsTrigger>
            ))}
          </TabsList>

          {policies.map(policy => (
            <TabsContent key={policy.id} value={policy.id} className="space-y-6">
              {/* Policy Header */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between">
                    <div>
                      <Input
                        value={policy.name}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPolicies(prev => prev.map(p =>
                          p.id === policy.id ? { ...p, name: e.target.value } : p
                        ))}
                        className="text-xl font-bold border-none p-0 h-auto bg-transparent"
                      />
                      <Input
                        value={policy.description}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPolicies(prev => prev.map(p =>
                          p.id === policy.id ? { ...p, description: e.target.value } : p
                        ))}
                        className="text-sm text-gray-600 dark:text-gray-400 border-none p-0 h-auto bg-transparent mt-1"
                        placeholder="Policy description..."
                      />
                    </div>
                    <div className="flex gap-2">
                      <Button onClick={simulatePolicy} disabled={isSimulating} variant="outline">
                        <Play className="w-4 h-4 mr-2" />
                        {isSimulating ? 'Simulating...' : 'Simulate'}
                      </Button>
                      <Button onClick={savePolicy} variant="default">
                        <Save className="w-4 h-4 mr-2" />
                        Save Policy
                      </Button>
                    </div>
                  </CardTitle>
                </CardHeader>
              </Card>

              {/* Validation Errors */}
              {policy.validationErrors.length > 0 && (
                <Alert variant="destructive">
                  <AlertDescription>
                    <ul className="list-disc list-inside">
                      {policy.validationErrors.map((error, index) => (
                        <li key={index}>{error}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}

              {/* Element Palette */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center">
                    <Plus className="w-5 h-5 mr-2" />
                    Add Policy Elements
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <h4 className="font-semibold text-sm">Conditions</h4>
                      {CONDITION_TYPES.map(condition => (
                        <Button
                          key={condition}
                          variant="outline"
                          size="sm"
                          className="w-full justify-start"
                          onClick={() => addElement('condition', {
                            name: condition,
                            config: { condition }
                          })}
                        >
                          {condition}
                        </Button>
                      ))}
                    </div>

                    <div className="space-y-2">
                      <h4 className="font-semibold text-sm">Actions</h4>
                      {AVAILABLE_ACTIONS.slice(0, 8).map(action => (
                        <Button
                          key={action}
                          variant="outline"
                          size="sm"
                          className="w-full justify-start"
                          onClick={() => addElement('action', {
                            name: action.toLowerCase().replace('_', ' '),
                            config: { action }
                          })}
                        >
                          {action}
                        </Button>
                      ))}
                    </div>

                    <div className="space-y-2">
                      <h4 className="font-semibold text-sm">Mission Phases</h4>
                      {MISSION_PHASES.map(phase => (
                        <Button
                          key={phase}
                          variant="outline"
                          size="sm"
                          className="w-full justify-start"
                          onClick={() => addElement('phase', {
                            name: phase.toLowerCase().replace('_', ' '),
                            config: { phase }
                          })}
                        >
                          {phase}
                        </Button>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Policy Canvas */}
              <Card>
                <CardHeader>
                  <CardTitle>Policy Flow</CardTitle>
                </CardHeader>
                <CardContent>
                  <DragDropContext onDragEnd={onDragEnd}>
                    <Droppable droppableId="policy-elements">
                      {(provided) => (
                        <div
                          {...provided.droppableProps}
                          ref={provided.innerRef}
                          className="min-h-[400px] border-2 border-dashed border-gray-300 dark:border-gray-600 rounded-lg p-4"
                        >
                          {policy.elements.length === 0 ? (
                            <div className="text-center text-gray-500 dark:text-gray-400 py-8">
                              <Plus className="w-12 h-12 mx-auto mb-4 opacity-50" />
                              <p>Drag policy elements here to build your recovery strategy</p>
                            </div>
                          ) : (
                            <div className="space-y-4">
                              {policy.elements.map((element, index) => (
                                <Draggable key={element.id} draggableId={element.id} index={index}>
                                  {(provided, snapshot) => (
                                    <div
                                      ref={provided.innerRef}
                                      {...provided.draggableProps}
                                      {...provided.dragHandleProps}
                                      className={`p-4 border rounded-lg bg-white dark:bg-gray-800 shadow-sm ${
                                        snapshot.isDragging ? 'shadow-lg rotate-2' : ''
                                      }`}
                                    >
                                      <PolicyElementCard
                                        element={element}
                                        onUpdate={(updates) => updateElement(element.id, updates)}
                                        onRemove={() => removeElement(element.id)}
                                      />
                                    </div>
                                  )}
                                </Draggable>
                              ))}
                            </div>
                          )}
                          {provided.placeholder}
                        </div>
                      )}
                    </Droppable>
                  </DragDropContext>
                </CardContent>
              </Card>

              {/* Simulation Results */}
              {simulationResults && (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center">
                      <Eye className="w-5 h-5 mr-2" />
                      Simulation Results
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      <div>
                        <h4 className="font-semibold mb-2">Mock Anomaly Input:</h4>
                        <pre className="bg-gray-100 dark:bg-gray-800 p-3 rounded text-sm overflow-x-auto">
                          {JSON.stringify(simulationResults.anomaly, null, 2)}
                        </pre>
                      </div>

                      <div>
                        <h4 className="font-semibold mb-2">Triggered Elements:</h4>
                        <div className="space-y-2">
                          {simulationResults.triggeredElements.map((element: PolicyElement, idx: number) => (
                            <Badge key={idx} variant="secondary">
                              {element.name}
                            </Badge>
                          ))}
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="font-semibold">Validation:</span>
                        <Badge variant={simulationResults.validationPassed ? "default" : "destructive"}>
                          {simulationResults.validationPassed ? "Passed" : "Failed"}
                        </Badge>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </TabsContent>
          ))}
        </Tabs>
      </div>
    </div>
  )
}

function PolicyElementCard({
  element,
  onUpdate,
  onRemove
}: {
  element: PolicyElement
  onUpdate: (updates: Partial<PolicyElement>) => void
  onRemove: () => void
}) {
  const getElementIcon = (type: string) => {
    switch (type) {
      case 'condition': return '🔍'
      case 'action': return '⚡'
      case 'phase': return '🚀'
      default: return '📄'
    }
  }

  const getElementColor = (type: string) => {
    switch (type) {
      case 'condition': return 'bg-blue-100 dark:bg-blue-900 border-blue-300'
      case 'action': return 'bg-green-100 dark:bg-green-900 border-green-300'
      case 'phase': return 'bg-purple-100 dark:bg-purple-900 border-purple-300'
      default: return 'bg-gray-100 dark:bg-gray-900 border-gray-300'
    }
  }

  return (
    <div className={`border-2 rounded-lg p-4 ${getElementColor(element.type)}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">{getElementIcon(element.type)}</span>
          <Badge variant="outline" className="capitalize">
            {element.type}
          </Badge>
        </div>
        <Button variant="ghost" size="sm" onClick={onRemove}>
          <Trash2 className="w-4 h-4" />
        </Button>
      </div>

      <div className="space-y-3">
        <div>
          <Label htmlFor={`name-${element.id}`}>Name</Label>
          <Input
            id={`name-${element.id}`}
            value={element.name}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => onUpdate({ name: e.target.value })}
            className="mt-1"
          />
        </div>

        {element.type === 'condition' && (
          <div>
            <Label htmlFor={`condition-${element.id}`}>Condition Expression</Label>
            <Input
              id={`condition-${element.id}`}
              value={element.config.condition || ''}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => onUpdate({
                config: { ...element.config, condition: e.target.value }
              })}
              placeholder="e.g., severity >= 0.8"
              className="mt-1"
            />
          </div>
        )}

        {element.type === 'action' && (
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label htmlFor={`action-${element.id}`}>Action Type</Label>
              <Select
                value={element.config.action || ''}
                onValueChange={(value: string) => onUpdate({
                  config: { ...element.config, action: value }
                })}
              >
                <SelectTrigger className="mt-1">
                  <SelectValue placeholder="Select action" />
                </SelectTrigger>
                <SelectContent>
                  {AVAILABLE_ACTIONS.map(action => (
                    <SelectItem key={action} value={action}>
                      {action}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor={`timeout-${element.id}`}>Timeout (s)</Label>
              <Input
                id={`timeout-${element.id}`}
                type="number"
                value={element.config.timeout || 30}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => onUpdate({
                  config: { ...element.config, timeout: parseInt(e.target.value) }
                })}
                className="mt-1"
              />
            </div>
          </div>
        )}

        {element.type === 'phase' && (
          <div>
            <Label htmlFor={`phase-${element.id}`}>Mission Phase</Label>
            <Select
              value={element.config.phase || ''}
              onValueChange={(value: string) => onUpdate({
                config: { ...element.config, phase: value }
              })}
            >
              <SelectTrigger className="mt-1">
                <SelectValue placeholder="Select phase" />
              </SelectTrigger>
              <SelectContent>
                {MISSION_PHASES.map(phase => (
                  <SelectItem key={phase} value={phase}>
                    {phase}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        <div className="text-xs text-gray-500 dark:text-gray-400">
          Drag to reorder • Click to configure
        </div>
      </div>
    </div>
  )
}

function getDefaultConfig(type: PolicyElement['type']): Record<string, any> {
  switch (type) {
    case 'condition':
      return { condition: 'severity >= 0.7' }
    case 'action':
      return { action: 'LOG_EVENT', timeout: 30 }
    case 'phase':
      return { phase: 'NOMINAL_OPS' }
    default:
      return {}
  }
}

function evaluateCondition(condition: string, context: any): boolean {
  // Simple condition evaluator - in real implementation, this would be more sophisticated
  try {
    // Replace variable references with actual values
    let expr = condition
      .replace(/severity/g, context.severity?.toString() || '0')
      .replace(/recurrence_count/g, context.recurrence_count?.toString() || '0')
      .replace(/component_health/g, `'${context.component_health || 'healthy'}'`)
      .replace(/resource_usage/g, context.resource_usage?.toString() || '0')

    // Simple evaluation (in production, use a proper expression evaluator)
    return eval(expr)
  } catch {
    return false
  }
}